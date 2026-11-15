"""Offline analysis of benchmark raw.json and sanitized per-role JSONL spans."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


STAGES = {
    "reserve": "botkernel.postgresql.reserve_and_outbox",
    "load": "botkernel.outbox.load",
    "publish": "botkernel.kafka.publish",
    "consume": "botkernel.kafka.consume",
    "execute": "botkernel.action.execute",
    "finalize": "botkernel.postgresql.finalize_action",
}


def _hex(value, length):
    return isinstance(value, str) and bool(re.fullmatch(f"[0-9a-f]{{{length}}}", value)) and int(value, 16) != 0


def _carrier(value):
    if not isinstance(value, dict):
        return None
    parent = value.get("traceparent")
    if not isinstance(parent, str) or not re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}", parent):
        return None
    trace_id, span_id = parent.split("-")[1:3]
    return (trace_id, span_id) if _hex(trace_id, 32) and _hex(span_id, 16) else None


def _stats(values, total):
    # Keep this module independent of the workload's database/driver imports.
    def percentile(p):
        if not values:
            return None
        ordered = sorted(values)
        index = (len(ordered) - 1) * p / 100
        lower = int(index)
        return round(ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (index - lower), 3)
    return {"n": len(values), "missing_actions": total - len(values),
            "negative_count": sum(v < 0 for v in values),
            **{f"p{p}": percentile(p) for p in (50, 95, 99)}}


def analyze(raw, spans):
    measured = {s["action_id"] for s in raw.get("samples", [])
                if s.get("phase") == "measured" and s.get("action_id")}
    anchors = defaultdict(set)
    trace_actions = defaultdict(set)
    invalid_provenance = 0
    for row in raw.get("summary", {}).get("authoritative_rows", []):
        if row.get("id") not in measured:
            continue
        carrier = _carrier(row.get("trace_context"))
        if carrier is None:
            invalid_provenance += 1
        else:
            anchors[carrier].add(row["id"])
            trace_actions[carrier[0]].add(row["id"])
    valid, invalid, duplicates, conflicts = {}, 0, 0, 0
    for span in spans:
        if not isinstance(span, dict) or not (
            _hex(span.get("trace_id"), 32) and _hex(span.get("span_id"), 16)
            and isinstance(span.get("name"), str)
            and isinstance(span.get("attributes", {}), dict)
            and type(span.get("start_time_ns")) is int and type(span.get("end_time_ns")) is int
            and span["end_time_ns"] >= span["start_time_ns"] >= 0
            and (span.get("parent_span_id") is None or _hex(span["parent_span_id"], 16))
        ):
            invalid += 1
            continue
        key = (span["trace_id"], span["span_id"])
        if key in valid:
            duplicates += 1
            if valid[key] != span:
                conflicts += 1
            continue
        valid[key] = span
        action = span.get("attributes", {}).get("action.id")
        if isinstance(action, str) and action in measured:
            trace_actions[key[0]].add(action)

    grouped = defaultdict(lambda: defaultdict(list))
    names = {name: stage for stage, name in STAGES.items()}
    ambiguous = 0
    for key, span in valid.items():
        if span["name"] not in names:
            continue
        action = span.get("attributes", {}).get("action.id")
        # An explicit action ID always wins, including IDs outside the measured set.
        if action is None:
            cursor, seen, candidates = key, set(), set()
            while cursor not in seen:
                seen.add(cursor)
                candidates.update(anchors.get(cursor, ()))
                ancestor = valid.get(cursor)
                if ancestor is None:
                    break
                ancestor_action = ancestor.get("attributes", {}).get("action.id")
                if ancestor_action is not None:
                    candidates.add(ancestor_action)
                    break
                parent = ancestor.get("parent_span_id")
                if parent is None:
                    break
                cursor = (cursor[0], parent)
            if not candidates:
                candidates = trace_actions[key[0]]
            action = next(iter(candidates)) if len(candidates) == 1 else None
            if len(candidates) > 1:
                ambiguous += 1
        if isinstance(action, str) and action in measured:
            grouped[action][names[span["name"]]].append(span)

    metrics = {name: [] for name in ("outbox_wait_ms", "dispatch_start_to_consume_ms",
                                    "publication_ms", "worker_execute_ms", "finalization_ms")}
    repeated = Counter()
    for action in measured:
        stages = grouped[action]
        for stage, records in stages.items():
            records.sort(key=lambda s: (s["start_time_ns"], s["span_id"]))
            repeated[stage] += max(0, len(records) - 1)
        first = {stage: records[0] for stage, records in stages.items() if records}
        if "reserve" in first and "load" in first:
            metrics["outbox_wait_ms"].append((first["load"]["start_time_ns"] - first["reserve"]["end_time_ns"]) / 1e6)
        if "publish" in first and "consume" in first:
            consume = first["consume"]
            # Prefer the actual propagated producer parent for redeliveries/retries.
            publish = next((s for s in stages["publish"]
                            if s["trace_id"] == consume["trace_id"] and s["span_id"] == consume.get("parent_span_id")), None)
            if publish is not None or len(stages["publish"]) == 1:
                publish = publish or first["publish"]
                metrics["dispatch_start_to_consume_ms"].append((consume["start_time_ns"] - publish["start_time_ns"]) / 1e6)
        for stage, metric in (("publish", "publication_ms"), ("execute", "worker_execute_ms"),
                              ("finalize", "finalization_ms")):
            if stage in first:
                metrics[metric].append((first[stage]["end_time_ns"] - first[stage]["start_time_ns"]) / 1e6)
    total = len(measured)
    telemetry = raw.get("summary", {}).get("backlog_telemetry")
    return {
        "measured_actions": total,
        "measured_samples_without_action_id": sum(s.get("phase") == "measured" and not s.get("action_id") for s in raw.get("samples", [])),
        "metrics": {name: _stats(values, total) for name, values in metrics.items()},
        "stage_coverage": {stage: {"n": sum(bool(grouped[a].get(stage)) for a in measured),
                                   "missing_actions": sum(not grouped[a].get(stage) for a in measured)} for stage in STAGES},
        "invalid_spans": invalid, "duplicate_span_records": duplicates,
        "conflicting_span_records": conflicts, "invalid_or_missing_trace_context": invalid_provenance,
        "ambiguous_spans": ambiguous, "additional_stage_spans": dict(repeated),
        "backlog_telemetry": telemetry,
        "unavailable": (["backlog and consumer lag samples"] if telemetry is None else []) + ["CPU and memory (external orchestrator)"],
        "definitions": {
            "outbox_wait_ms": "outbox.load start minus reserve_and_outbox end",
            "dispatch_start_to_consume_ms": "consume start minus publish start; includes producer/broker/consumer scheduling, not pure Kafka networking",
            "publication_ms": "kafka.publish span duration",
            "worker_execute_ms": "action.execute span duration including lock, simulator and finalization",
            "finalization_ms": "postgresql.finalize_action span duration",
        },
        "notes": ["One first observed stage per measured action; additional attempts disclosed.",
                  "Cross-process wall-clock deltas retain negative values; negative_count discloses clock/order anomalies.",
                  "Missing or sampled-out spans remain missing coverage; telemetry samples may include warmup."],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--spans", required=True, nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    spans, malformed = [], 0
    for path in args.spans:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    spans.append(json.loads(line))
                except (ValueError, TypeError):
                    malformed += 1
    result = analyze(json.loads(args.raw.read_text(encoding="utf-8")), spans)
    result["malformed_jsonl_lines"] = malformed
    # Never replace historical raw files or earlier analysis.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
