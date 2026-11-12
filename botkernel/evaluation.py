"""Reproducible, local discrete-event evaluation of coordination strategies."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from botkernel.stability import HOLD_SECONDS, MAX_INTERVENTIONS, VERIFICATION_SAMPLES, VERIFICATION_SECONDS, analysis, latency
from botkernel.episode_metrics import score_episodes

MODES = ("independent", "basic", "collective")
MODE_LABELS = {
    "independent": "Independent agents",
    "basic": "Resource locks + fixed cooldown",
    "collective": "Collective Stability Controller",
}
SCENARIOS = (
    "oscillation",
    "healthy_scaling",
    "simultaneous_resources",
    "overlapping_remediation",
    "cascade",
    "recurrence",
    "temporary_spike",
    "worker_failure",
)
WINDOW_TICKS = 60
BASIC_COOLDOWN_TICKS = 10
RECOVERY_SAMPLES = 10


def _harmful_intervals(scenario: str, duration: int) -> list[tuple[int, int]]:
    end = max(1, duration - 45)
    if scenario in ("oscillation", "overlapping_remediation", "worker_failure"):
        return [(0, end)]
    if scenario == "cascade":
        return [(15, max(16, duration - 45))]
    if scenario == "recurrence":
        return [(0, 30), (60, end)] if end > 60 else [(0, end)]
    return []


def build_schedule(seed: int, scenario: str, duration: int) -> tuple[list[dict[str, Any]], str]:
    """Create the exogenous input schedule once for reuse across all strategies."""
    digest_seed = int.from_bytes(hashlib.sha256(scenario.encode("ascii")).digest()[:4], "big")
    rng = random.Random((seed << 32) ^ digest_seed)
    intervals = _harmful_intervals(scenario, duration)
    schedule: list[dict[str, Any]] = []
    for tick in range(duration):
        interaction_end = max(1, duration - 45)
        if scenario in ("oscillation", "overlapping_remediation", "worker_failure"):
            load_a, load_b = (12.0 if tick < interaction_end else 6.0), 6.0
        elif scenario == "healthy_scaling":
            load_a, load_b = float(6 + min(8, tick // 8)), 6.0
        elif scenario == "simultaneous_resources":
            load_a, load_b = float(6 + min(4, tick // 20)), float(6 + min(4, tick // 18))
        elif scenario == "cascade":
            load_a = 12.0 if 15 <= tick < interaction_end else 6.0
            load_b = 6.0
        elif scenario == "recurrence":
            active = tick < 30 or 60 <= tick < interaction_end
            load_a, load_b = (12.0 if active else 6.0), 6.0
        elif scenario == "temporary_spike":
            load_a, load_b = (16.0 if 30 <= tick < 33 else 6.0), 6.0
        else:
            raise ValueError(f"Unsupported scenario: {scenario}")
        noise_a = rng.uniform(-0.05, 0.05)
        noise_b = rng.uniform(-0.05, 0.05)
        schedule.append({
            "tick": tick,
            "load_a": round(load_a + noise_a, 3),
            "load_b": round(load_b + noise_b, 3),
            "harmful": any(start <= tick < stop for start, stop in intervals),
            "cost_pressure": (
                scenario in ("oscillation", "overlapping_remediation", "worker_failure")
                or (scenario == "cascade" and 15 <= tick < interaction_end)
                or (scenario == "recurrence" and (tick < 30 or 60 <= tick < interaction_end))
            ),
            "worker_available": not (scenario == "worker_failure" and 30 <= tick < 40),
        })
    encoded = json.dumps(schedule, sort_keys=True, separators=(",", ":")).encode()
    return schedule, hashlib.sha256(encoded).hexdigest()


def _proposals(
    scenario: str,
    state: dict[str, int],
    loads: dict[str, float],
    tick: int,
    cost_pressure: bool,
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    cost_resource = "service-a"
    cost_capacity = state[cost_resource]
    cost_load = loads[cost_resource]
    cost_latency = latency(cost_capacity, cost_load)
    if cost_pressure and cost_capacity > 4:
        proposals.append({"agent": "cost-agent", "resource": cost_resource, "target": cost_capacity - 1})
    elif scenario in ("healthy_scaling", "temporary_spike", "simultaneous_resources"):
        if cost_latency < 60 and cost_capacity > 4 and tick % 6 == 0:
            proposals.append({"agent": "cost-agent", "resource": cost_resource, "target": cost_capacity - 1})

    performance_resource = "service-b" if scenario == "simultaneous_resources" else "service-a"
    performance_capacity = state[performance_resource]
    performance_load = loads[performance_resource]
    if scenario == "cascade" and performance_resource == "service-b" and state["service-a"] <= 5:
        performance_load += 4
    performance_latency = latency(performance_capacity, performance_load)
    if performance_latency > 80 and performance_capacity < 18:
        proposals.append({
            "agent": "performance-agent",
            "resource": performance_resource,
            "target": performance_capacity + 1,
        })

    if scenario == "overlapping_remediation" and len(proposals) == 2:
        proposals.sort(key=lambda proposal: 0 if proposal["agent"] == ("cost-agent" if tick % 2 == 0 else "performance-agent") else 1)
    else:
        proposals.sort(key=lambda proposal: (proposal["resource"], proposal["agent"]))
    return proposals


def _new_incident(tick: int, reason: str) -> dict[str, Any]:
    return {
        "status": "HOLD",
        "hold_until": tick + HOLD_SECONDS,
        "monitor_started": tick,
        "verification_started": None,
        "healthy_samples": 0,
        "interventions": 1,
        "recurrences": 0,
        "opened_at": tick,
        "last_transition": reason,
        "events": [{"tick": tick, "transition": reason}],
    }


def _reintervene(incident: dict[str, Any], tick: int, reason: str) -> None:
    incident["interventions"] += 1
    incident["recurrences"] += 1
    incident["status"] = "HOLD"
    incident["hold_until"] = tick + HOLD_SECONDS
    incident["monitor_started"] = tick
    incident["verification_started"] = None
    incident["healthy_samples"] = 0
    incident["last_transition"] = reason
    incident["events"].append({"tick": tick, "transition": reason})


def _advance_collective(
    incident: dict[str, Any] | None,
    effects: list[dict[str, Any]],
    tick: int,
    latency_a: float,
) -> tuple[dict[str, Any] | None, int]:
    window = [effect for effect in effects if effect["tick"] >= tick - WINDOW_TICKS]
    if incident is None:
        if analysis(window)["detected"]:
            return _new_incident(tick, "detected and contained"), 1
        return None, 0

    monitor_effects = [effect for effect in effects if effect["tick"] > incident["monitor_started"]]
    unhealthy = analysis(monitor_effects)["detected"] or latency_a > 100
    if incident["status"] == "HOLD":
        if tick < incident["hold_until"]:
            return incident, 0
        if unhealthy:
            if incident["interventions"] >= MAX_INTERVENTIONS:
                incident["status"] = "ESCALATED"
                incident["last_transition"] = "intervention limit reached"
                incident["events"].append({"tick": tick, "transition": incident["last_transition"]})
                return incident, 0
            _reintervene(incident, tick, "harmful behavior persisted after hold")
            return incident, 1
        incident["status"] = "VERIFYING"
        incident["verification_started"] = tick
        incident["healthy_samples"] = 1
        incident["events"].append({"tick": tick, "transition": "sustained verification started"})
        return incident, 0

    if incident["status"] == "VERIFYING":
        if unhealthy:
            if incident["interventions"] >= MAX_INTERVENTIONS:
                incident["status"] = "ESCALATED"
                incident["last_transition"] = "verification failed; intervention limit reached"
                incident["events"].append({"tick": tick, "transition": incident["last_transition"]})
                return incident, 0
            _reintervene(incident, tick, "verification failed; recurrence contained")
            return incident, 1
        incident["healthy_samples"] += 1
        if (
            incident["healthy_samples"] >= VERIFICATION_SAMPLES
            and tick - incident["verification_started"] >= VERIFICATION_SECONDS
        ):
            incident["status"] = "VERIFIED"
            incident["monitor_started"] = tick
            incident["events"].append({"tick": tick, "transition": "sustained recovery verified"})
        return incident, 0

    if incident["status"] == "VERIFIED":
        verified_window = [effect for effect in effects if effect["tick"] > incident["monitor_started"]]
        if analysis(verified_window)["detected"]:
            if incident["interventions"] >= MAX_INTERVENTIONS:
                incident["status"] = "ESCALATED"
                incident["last_transition"] = "verified incident recurred after intervention limit"
                incident["events"].append({"tick": tick, "transition": incident["last_transition"]})
                return incident, 0
            _reintervene(incident, tick, "verified incident recurred")
            return incident, 1
    return incident, 0


def simulate(seed: int, scenario: str, duration: int, mode: str) -> dict[str, Any]:
    """Simulate one strategy against one immutable seeded workload schedule."""
    if mode not in MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    schedule, digest = build_schedule(seed, scenario, duration)
    capacities = {"service-a": 6, "service-b": 6}
    effects: list[dict[str, Any]] = []
    ticks: list[dict[str, Any]] = []
    interventions: list[dict[str, Any]] = []
    incident: dict[str, Any] | None = None
    basic_consecutive = {"service-a": 0, "service-b": 0}
    basic_cooldown_until = {"service-a": -1, "service-b": -1}
    basic_alarm_until = {"service-a": -1, "service-b": -1}
    stable_run = 0
    completed = 0
    conflicts = 0
    worker_rejections = 0
    recurrences = 0

    for inputs in schedule:
        tick = inputs["tick"]
        loads = {"service-a": inputs["load_a"], "service-b": inputs["load_b"]}
        current_latency_a = latency(capacities["service-a"], loads["service-a"])
        status = incident["status"] if incident else "NONE"
        collective_hold = mode == "collective" and bool(
            incident
            and incident["status"] in ("VERIFYING", "ESCALATED")
            or incident
            and incident["status"] == "HOLD"
            and tick < incident["hold_until"]
        )
        basic_hold = mode == "basic"
        proposals = _proposals(scenario, capacities, loads, tick, inputs["cost_pressure"])
        changed_resources: set[str] = set()
        tick_reversals = 0
        for proposal in proposals:
            resource = proposal["resource"]
            if not inputs["worker_available"]:
                worker_rejections += 1
                continue
            if resource in changed_resources:
                conflicts += 1
                continue
            delta = proposal["target"] - capacities[resource]
            if delta < 0 and (
                (collective_hold and mode == "collective")
                or (basic_hold and tick < basic_cooldown_until[resource])
            ):
                continue
            if not delta:
                continue
            before = capacities[resource]
            after = proposal["target"]
            effect_latency = latency(after, loads[resource])
            previous = next((effect for effect in reversed(effects) if effect["resource"] == resource), None)
            if previous:
                previous_direction = previous["after_capacity"] - previous["before_capacity"]
                if previous_direction * delta < 0 and previous["agent"] != proposal["agent"]:
                    tick_reversals += 1
            event = {
                "seed": seed,
                "scenario": scenario,
                "mode": mode,
                "tick": tick,
                "action_id": f"{seed}:{scenario}:{mode}:{tick}:{proposal['agent']}",
                "resource": resource,
                "agent": proposal["agent"],
                "before_capacity": before,
                "after_capacity": after,
                "latency": effect_latency,
                "workload": loads[resource],
            }
            capacities[resource] = after
            changed_resources.add(resource)
            effects.append(event)
            completed += 1

        current_latency_a = latency(capacities["service-a"], loads["service-a"])
        effective_load_b = loads["service-b"] + (
            4 if scenario == "cascade" and capacities["service-a"] <= 5 else 0
        )
        current_latency_b = latency(capacities["service-b"], effective_load_b)
        application_latency = max(current_latency_a, current_latency_b)
        intervention_added = 0
        if mode == "basic":
            for resource, current_latency in (
                ("service-a", current_latency_a),
                ("service-b", current_latency_b),
            ):
                basic_consecutive[resource] = (
                    basic_consecutive[resource] + 1 if current_latency > 100 else 0
                )
                if basic_consecutive[resource] >= 2 and tick >= basic_cooldown_until[resource]:
                    basic_cooldown_until[resource] = tick + BASIC_COOLDOWN_TICKS
                    basic_alarm_until[resource] = basic_cooldown_until[resource]
                    intervention_added += 1
                    basic_consecutive[resource] = 0
                    interventions.append({
                        "tick": tick,
                        "resource": resource,
                        "reason": "two consecutive resource latency samples above 100 ms",
                        "ground_truth_harmful": inputs["harmful"],
                    })
        elif mode == "collective":
            previous_status = incident["status"] if incident else "NONE"
            resource_effects = [effect for effect in effects if effect["resource"] == "service-a"]
            incident, intervention_added = _advance_collective(incident, resource_effects, tick, current_latency_a)
            if incident and incident["status"] == "HOLD" and intervention_added:
                interventions.append({
                    "tick": tick,
                    "reason": incident["last_transition"],
                    "ground_truth_harmful": inputs["harmful"],
                })
            if incident and previous_status == "VERIFIED" and incident["status"] == "HOLD":
                recurrences += 1

        if mode == "independent":
            alarm = False
        elif mode == "basic":
            alarm = any(tick < until for until in basic_alarm_until.values())
        else:
            alarm = bool(incident and incident["status"] in ("HOLD", "VERIFYING", "ESCALATED"))

        if application_latency <= 100 and tick_reversals == 0:
            stable_run += 1
        else:
            stable_run = 0
        ticks.append({
            "seed": seed,
            "scenario": scenario,
            "mode": mode,
            "tick": tick,
            "ground_truth_harmful": inputs["harmful"],
            "alarm_active": alarm,
            "capacity_a": capacities["service-a"],
            "capacity_b": capacities["service-b"],
            "workload_a": inputs["load_a"],
            "workload_b": effective_load_b,
            "latency_a_ms": current_latency_a,
            "latency_b_ms": current_latency_b,
            "application_latency_ms": application_latency,
            "intervention_count": len(interventions),
            "incident_status": incident["status"] if incident else (
                "COOLDOWN" if mode == "basic" and any(tick < until for until in basic_cooldown_until.values()) else "NONE"
            ),
            "stable_ticks": stable_run,
            "worker_available": inputs["worker_available"],
        })
    tp = sum(1 for row in ticks if row["ground_truth_harmful"] and row["alarm_active"])
    fp = sum(1 for row in ticks if not row["ground_truth_harmful"] and row["alarm_active"])
    fn = sum(1 for row in ticks if row["ground_truth_harmful"] and not row["alarm_active"])
    tn = sum(1 for row in ticks if not row["ground_truth_harmful"] and not row["alarm_active"])
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1_denominator = 2 * tp + fp + fn
    f1 = 2 * tp / f1_denominator if f1_denominator else None
    directions: dict[str, tuple[int, str]] = {}
    oscillations = 0
    for effect in effects:
        direction = effect["after_capacity"] - effect["before_capacity"]
        previous = directions.get(effect["resource"])
        if previous and previous[0] * direction < 0 and previous[1] != effect["agent"]:
            oscillations += 1
        directions[effect["resource"]] = (direction, effect["agent"])

    intervals = _harmful_intervals(scenario, duration)
    episode_scores = score_episodes(intervals, [row["alarm_active"] for row in ticks])
    onset_delays = episode_scores["episode_detection_delays_ticks"]
    clear_delays = [value for value in episode_scores["episode_clear_delays_ticks"] if value is not None]
    harmful_ticks = [row for row in ticks if row["ground_truth_harmful"]]
    detection_delays: list[int | None] = []
    for start, stop in intervals:
        first = next((row["tick"] for row in ticks if start <= row["tick"] < stop and row["alarm_active"]), None)
        detection_delays.append(first - start if first is not None else None)
    lifecycle = incident["events"] if incident else []
    episode_outcomes = []
    for index, (start, _) in enumerate(intervals):
        episode_limit = intervals[index + 1][0] if index + 1 < len(intervals) else duration
        if mode == "collective":
            verified = [
                event["tick"]
                for event in lifecycle
                if event["transition"] == "sustained recovery verified"
                and start <= event["tick"] < episode_limit
            ]
            recurred = [
                event["tick"]
                for event in lifecycle
                if "recurred" in event["transition"]
                and start <= event["tick"] < episode_limit
            ]
            valid_verifications = [
                verified_tick
                for verified_tick in verified
                if not any(verified_tick < recurrence_tick < episode_limit for recurrence_tick in recurred)
            ]
            recovery = valid_verifications[-1] if valid_verifications else None
        else:
            recovery = next(
                (
                    row["tick"]
                    for row in ticks
                    if start <= row["tick"] < episode_limit
                    and row["stable_ticks"] >= RECOVERY_SAMPLES
                ),
                None,
            )
        escalation = next(
            (
                event["tick"]
                for event in lifecycle
                if "escalat" in event["transition"]
                and start <= event["tick"] < episode_limit
            ),
            None,
        )
        resolution = recovery if recovery is not None else escalation
        episode_outcomes.append({
            "start": start,
            "recovered_at": recovery,
            "escalated_at": escalation,
            "resolution_delay_ticks": resolution - start if resolution is not None else None,
            "outcome": "VERIFIED" if recovery is not None else "ESCALATED" if escalation is not None else "UNRESOLVED",
        })
    recovery_delays = [
        item["recovered_at"] - item["start"]
        for item in episode_outcomes
        if item["recovered_at"] is not None
    ]
    escalation_delays = [
        item["escalated_at"] - item["start"]
        for item in episode_outcomes
        if item["escalated_at"] is not None
    ]
    resolution_delays = [
        item["resolution_delay_ticks"]
        for item in episode_outcomes
        if item["resolution_delay_ticks"] is not None
    ]
    stable_success = len(recovery_delays) / len(intervals) if intervals else None
    recovery_tick = statistics.mean(recovery_delays) if recovery_delays else None
    escalation_tick = statistics.mean(escalation_delays) if escalation_delays else None
    recovery_or_escalation_tick = statistics.mean(resolution_delays) if resolution_delays else None
    incident_status = incident["status"] if incident else "NONE"
    return {
        "seed": seed,
        "scenario": scenario,
        "mode": mode,
        "duration_ticks": duration,
        "input_digest": digest,
        "harmful_intervals": [{"start": start, "stop": stop} for start, stop in intervals],
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        **episode_scores,
        "mean_episode_detection_delay_ticks": statistics.mean(onset_delays) if onset_delays else None,
        "mean_episode_clear_delay_ticks": statistics.mean(clear_delays) if clear_delays else None,
        "containment_active_ticks": sum(
            row["incident_status"] in ("COOLDOWN", "HOLD", "VERIFYING", "ESCALATED") for row in ticks
        ),
        "healthy_latency_fraction_during_harm": (
            sum(row["application_latency_ms"] <= 100 for row in harmful_ticks) / len(harmful_ticks)
            if harmful_ticks else None
        ),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
        "detection_delays_ticks": detection_delays,
        "mean_detection_delay_ticks": statistics.mean([value for value in detection_delays if value is not None]) if any(value is not None for value in detection_delays) else None,
        "oscillating_resource_changes": oscillations,
        "intervention_count": len(interventions),
        "unnecessary_interventions": sum(not item["ground_truth_harmful"] for item in interventions),
        "incident_recurrences": recurrences,
        "sustained_stabilization_success": stable_success,
        "stabilization_successes": len(recovery_delays),
        "stabilization_episodes": len(intervals),
        "time_to_recovery_ticks": recovery_tick,
        "time_to_recovery_delays_ticks": recovery_delays,
        "time_to_escalation_ticks": escalation_tick,
        "time_to_recovery_or_escalation_ticks": recovery_or_escalation_tick,
        "episode_outcomes": episode_outcomes,
        "final_incident_status": incident_status,
        "application_latency_mean_ms": statistics.mean(row["application_latency_ms"] for row in ticks),
        "application_latency_p95_ms": _percentile([row["application_latency_ms"] for row in ticks], .95),
        "mean_capacity_a": statistics.mean(row["capacity_a"] for row in ticks),
        "mean_capacity_b": statistics.mean(row["capacity_b"] for row in ticks),
        "completed_actions": completed,
        "logical_actions_per_virtual_second": completed / duration,
        "resource_lock_conflicts": conflicts,
        "worker_unavailable_rejections": worker_rejections,
        "admission_latency_p50_ms": None,
        "admission_latency_p95_ms": None,
        "dispatch_latency_p50_ms": None,
        "dispatch_latency_p95_ms": None,
        "cpu_usage": None,
        "memory_usage_bytes": None,
        "interventions": interventions,
        "incident_lifecycle": incident["events"] if incident else [],
        "ticks": ticks,
        "effects": effects,
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[index], 3)


def _mean_ci(values: list[float | int | None]) -> dict[str, float | int | None]:
    present = [float(value) for value in values if value is not None]
    if not present:
        return {"mean": None, "ci95_low": None, "ci95_high": None, "n": 0}
    mean = statistics.mean(present)
    margin = 1.96 * statistics.stdev(present) / math.sqrt(len(present)) if len(present) > 1 else None
    return {
        "mean": round(mean, 4),
        "ci95_low": round(mean - margin, 4) if margin is not None else None,
        "ci95_high": round(mean + margin, 4) if margin is not None else None,
        "n": len(present),
    }


def _summaries(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for scenario in sorted({run["scenario"] for run in runs}):
        for mode in MODES:
            selected = [run for run in runs if run["scenario"] == scenario and run["mode"] == mode]
            summary: dict[str, Any] = {
                "scenario": scenario,
                "mode": mode,
                "mode_label": MODE_LABELS[mode],
                "seed_count": len({run["seed"] for run in selected}),
            }
            for metric in (
                "precision", "recall", "f1", "false_positive_rate",
                "episode_true_positives", "episode_false_positives", "episode_false_negatives",
                "episode_precision", "episode_recall", "mean_episode_detection_delay_ticks",
                "alert_onsets_outside_truth", "unmatched_alerts_overlapping_truth",
                "mean_episode_clear_delay_ticks", "containment_active_ticks", "healthy_latency_fraction_during_harm",
                "mean_detection_delay_ticks", "oscillating_resource_changes",
                "intervention_count", "unnecessary_interventions", "incident_recurrences",
                "sustained_stabilization_success", "time_to_recovery_ticks",
                "time_to_escalation_ticks", "time_to_recovery_or_escalation_ticks",
                "application_latency_mean_ms", "application_latency_p95_ms",
                "mean_capacity_a", "mean_capacity_b", "completed_actions", "logical_actions_per_virtual_second",
            ):
                values = [run[metric] for run in selected]
                summary[metric] = _mean_ci(values)
            summaries.append(summary)
    return summaries


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, separators=(",", ":")) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            })


def _report(run_id: str, seeds: list[int], scenarios: list[str], duration: int, summaries: list[dict[str, Any]]) -> str:
    lines = [
        f"# BotKernel evaluation {run_id}",
        "",
        "This is a deterministic discrete-event simulation, not a PostgreSQL/Kafka throughput benchmark.",
        "All modes share the same per-seed, per-scenario exogenous schedule and ground-truth intervals.",
        "Ground truth is declared by scenario schedule before detectors execute; it does not depend on alarms.",
        "The first table reports tick-level alarm occupancy, not incident episodes.",
        f"Seeds: `{seeds}`. Scenarios: `{', '.join(scenarios)}`. Duration: `{duration}` virtual seconds per case.",
        "",
        "## Strategy results",
        "",
        "| Scenario | Mode | Precision | Recall | F1 | FP rate | Detection delay (s) | Oscillations | Interventions | Recurrences | Stabilized | Recovery / escalation (s) | App p95 (ms) | Actions/sim-s |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        def display(metric: str) -> str:
            interval = row[metric]
            value = interval["mean"]
            if value is None:
                return "n/a"
            if interval["ci95_low"] is None:
                return f"{value:.3f}"
            return f"{value:.3f} [{interval['ci95_low']:.3f}, {interval['ci95_high']:.3f}]"
        lines.append(
            f"| {row['scenario']} | {row['mode']} | {display('precision')} | {display('recall')} | "
            f"{display('f1')} | {display('false_positive_rate')} | {display('mean_detection_delay_ticks')} | "
            f"{display('oscillating_resource_changes')} | {display('intervention_count')} | "
            f"{display('incident_recurrences')} | {display('sustained_stabilization_success')} | "
            f"{display('time_to_recovery_or_escalation_ticks')} | {display('application_latency_p95_ms')} | "
            f"{display('logical_actions_per_virtual_second')} |"
        )
    lines.extend([
        "",
        "## Episode-level detection",
        "",
        "Alerts are maximal contiguous alarm intervals; sorted harmful and alert intervals are matched one-to-one on overlap.",
        "Extra alerts overlapping a matched harmful episode count as unmatched, not necessarily false onsets; raw runs distinguish them.",
        "A persistent alert spanning two harmful intervals can match only the first; end-of-run active alerts have censored clear time.",
        "",
        "| Scenario | Mode | Episode precision | Episode recall | False episodes | Missed episodes | Detection delay | Clear delay | Containment ticks | Healthy latency during harm |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in summaries:
        def display_episode(metric: str) -> str:
            mean = row[metric]["mean"]
            return "n/a" if mean is None else f"{mean:.3f}"
        lines.append(
            f"| {row['scenario']} | {row['mode']} | {display_episode('episode_precision')} | "
            f"{display_episode('episode_recall')} | {display_episode('episode_false_positives')} | "
            f"{display_episode('episode_false_negatives')} | {display_episode('mean_episode_detection_delay_ticks')} | "
            f"{display_episode('mean_episode_clear_delay_ticks')} | {display_episode('containment_active_ticks')} | "
            f"{display_episode('healthy_latency_fraction_during_harm')} |"
        )
    lines.extend([
        "",
        "## Interpretation limits",
        "",
        "- Application latency and logical action throughput are produced by the deterministic simulator.",
        "- Admission/dispatch percentiles, CPU, and memory are null because this harness does not execute database or Kafka operations.",
        "- Confidence intervals are normal-approximation 95% intervals over per-seed scenario runs; they are descriptive and weak with few seeds.",
        "- `independent` retains per-resource serialization and quota safety. It disables collective alarms/interventions.",
        "- `basic` uses per-resource serialization, a two-sample 100 ms threshold, and a fixed 10-second scale-down cooldown.",
        "- `collective` calls the production `stability.analysis` scoring function and applies its hold, verification, recurrence, and escalation limits in virtual time.",
        "- The workload model, synthetic latency formula, and ground-truth labels are experimental assumptions, not production telemetry or causal proof.",
    ])
    return "\n".join(lines) + "\n"


def run_evaluation(
    seeds: list[int],
    scenarios: list[str],
    duration: int,
    output_dir: str | Path,
) -> dict[str, Any]:
    if not 120 <= duration <= 180:
        raise ValueError("duration must be between 120 and 180 virtual seconds")
    if not 1 <= len(seeds) <= 5 or len(set(seeds)) != len(seeds):
        raise ValueError("provide 1..5 unique seeds")
    if not scenarios or len(set(scenarios)) != len(scenarios) or any(scenario not in SCENARIOS for scenario in scenarios):
        raise ValueError("scenarios must be a non-empty, unique subset of the supported scenarios")
    run_id = str(uuid.uuid4())
    directory = Path(output_dir) / run_id
    directory.mkdir(parents=True, exist_ok=False)
    created_at = datetime.now(timezone.utc).isoformat()
    runs = [
        simulate(seed, scenario, duration, mode)
        for seed in seeds
        for scenario in scenarios
        for mode in MODES
    ]
    summaries = _summaries(runs)
    tick_rows = [tick for run in runs for tick in run["ticks"]]
    effect_rows = [effect for run in runs for effect in run["effects"]]
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": created_at,
        "experiment_kind": "deterministic_discrete_event_simulation",
        "seeds": seeds,
        "scenarios": scenarios,
        "duration_ticks": duration,
        "modes": [{"id": mode, "label": MODE_LABELS[mode]} for mode in MODES],
        "configuration": {
            "window_ticks": WINDOW_TICKS,
            "basic_cooldown_ticks": BASIC_COOLDOWN_TICKS,
            "hold_ticks": HOLD_SECONDS,
            "verification_ticks": VERIFICATION_SECONDS,
            "verification_samples": VERIFICATION_SAMPLES,
            "max_interventions": MAX_INTERVENTIONS,
            "ground_truth": {scenario: _harmful_intervals(scenario, duration) for scenario in scenarios},
            "backend_performance_metrics": "not measured by this offline simulator",
        },
        "summaries": summaries,
        "runs": runs,
    }
    (directory / "raw.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    _write_csv(directory / "summary.csv", summaries)
    _write_csv(directory / "ticks.csv", tick_rows)
    _write_csv(directory / "effects.csv", effect_rows)
    (directory / "report.md").write_text(_report(run_id, seeds, scenarios, duration, summaries), encoding="utf-8")
    (directory / "history.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "created_at": created_at,
                "scenarios": scenarios,
                "seeds": seeds,
                "duration_ticks": duration,
                "summaries": summaries,
            },
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    return {
        "run_id": run_id,
        "created_at": created_at,
        "seeds": seeds,
        "scenarios": scenarios,
        "duration_ticks": duration,
        "summaries": summaries,
        "result_dir": str(directory),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 23, 41])
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results"))
    args = parser.parse_args()
    result = run_evaluation(args.seeds, args.scenarios, args.duration, args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "summaries"}, indent=2))
    print(f"Results: {result['result_dir']}")


if __name__ == "__main__":
    main()
