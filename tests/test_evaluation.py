import csv
import json

import pytest

from botkernel.evaluation import MODES, SCENARIOS, build_schedule, run_evaluation, simulate


def test_seeded_schedules_are_identical_across_modes_and_reproducible():
    schedule_a, digest_a = build_schedule(27, "recurrence", 100)
    schedule_b, digest_b = build_schedule(27, "recurrence", 100)
    assert schedule_a == schedule_b
    assert digest_a == digest_b

    collective = simulate(27, "oscillation", 100, "collective")
    replay = simulate(27, "oscillation", 100, "collective")
    independent = simulate(27, "oscillation", 100, "independent")
    assert collective["input_digest"] == independent["input_digest"]
    assert collective["effects"] == replay["effects"]
    assert collective["incident_lifecycle"] == replay["incident_lifecycle"]
    assert collective["tp"] > 0


def test_scenario_ground_truth_is_independent_and_healthy_spike_is_negative():
    spike = simulate(5, "temporary_spike", 100, "basic")
    assert not any(row["ground_truth_harmful"] for row in spike["ticks"])
    assert spike["unnecessary_interventions"] >= 0
    assert all(value is None for value in (
        spike["admission_latency_p50_ms"],
        spike["dispatch_latency_p95_ms"],
        spike["cpu_usage"],
    ))

    healthy = simulate(5, "healthy_scaling", 120, "collective")
    assert healthy["precision"] is None
    assert healthy["recall"] is None
    assert healthy["f1"] is None
    assert healthy["false_positive_rate"] == 0

    cascade = simulate(5, "cascade", 120, "collective")
    assert cascade["harmful_intervals"] == [{"start": 15, "stop": 75}]
    assert cascade["final_incident_status"] in {"HOLD", "VERIFYING", "VERIFIED", "ESCALATED", "NONE"}
    assert cascade["time_to_recovery_ticks"] is None or cascade["time_to_recovery_ticks"] >= 0


def test_scenario_coverage_and_worker_failure_are_recorded():
    assert set(SCENARIOS) == {
        "oscillation", "healthy_scaling", "simultaneous_resources", "overlapping_remediation",
        "cascade", "recurrence", "temporary_spike", "worker_failure",
    }
    worker = simulate(12, "worker_failure", 100, "independent")
    assert worker["worker_unavailable_rejections"] > 0
    assert {row["mode"] for row in [simulate(12, "worker_failure", 100, mode) for mode in MODES]} == set(MODES)


def test_evaluation_persists_raw_csv_and_report(tmp_path):
    result = run_evaluation([3, 11], ["oscillation", "healthy_scaling"], 120, tmp_path)
    directory = tmp_path / result["run_id"]
    payload = json.loads((directory / "raw.json").read_text(encoding="utf-8"))
    assert len(payload["runs"]) == 2 * 2 * 3
    assert len(payload["summaries"]) == 2 * 3
    history = json.loads((directory / "history.json").read_text(encoding="utf-8"))
    assert history["summaries"] == payload["summaries"]
    assert (directory / "report.md").is_file()
    with (directory / "ticks.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2 * 2 * 3 * 120
    assert {row["mode"] for row in rows} == set(MODES)


def test_experiment_api_runs_bounded_comparison_and_serves_saved_artifacts(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from botkernel.api import app
    import botkernel.api as api

    monkeypatch.setattr(api, "EXPERIMENT_RESULTS", tmp_path)
    client = TestClient(app)
    response = client.post(
        "/experiments",
        json={"scenario": "healthy_scaling", "seeds": [17, 23], "duration": 120},
    )
    assert response.status_code == 201
    result = response.json()
    assert {row["mode"] for row in result["summaries"]} == set(MODES)
    assert len(result["time_series"]) == 3 * 120
    assert client.get("/experiments").status_code == 200
    history = client.get("/experiments").json()
    assert len(history) == 1
    assert history[0]["summaries"] == result["summaries"]
    assert "time_series" not in history[0]
    artifact = client.get(result["artifacts"]["summary.csv"])
    assert artifact.status_code == 200
    assert "scenario,mode" in artifact.text
    assert client.get("/experiments/not-a-uuid").status_code == 422
    assert client.post(
        "/experiments",
        json={"scenario": "oscillation", "seeds": [17, 17], "duration": 120},
    ).status_code == 422


def test_experiment_history_does_not_build_unrequested_time_series():
    from botkernel.api import _experiment_detail

    class UnreadableRuns:
        def __iter__(self):
            pytest.fail("history summary must not traverse tick data")

    payload = {
        "runs": UnreadableRuns(),
        "run_id": "history-summary",
        "created_at": "2026-11-12T00:00:00Z",
        "scenarios": ["oscillation"],
        "seeds": [17],
        "duration_ticks": 120,
        "summaries": [],
    }
    result = _experiment_detail(payload, include_series=False)
    assert "time_series" not in result


def test_legacy_experiment_history_avoids_loading_raw_ticks(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import botkernel.api as api
    from botkernel.api import app
    from uuid import uuid4

    monkeypatch.setattr(api, "EXPERIMENT_RESULTS", tmp_path)
    run_id = str(uuid4())
    directory = tmp_path / run_id
    directory.mkdir()
    (directory / "report.md").write_text(
        f"Seeds: `[17, 23]`. Scenarios: `oscillation`. Duration: `120` virtual seconds per case.\n",
        encoding="utf-8",
    )
    (directory / "summary.csv").write_text(
        'scenario,mode,precision\noscillation,collective,"{""mean"":0.5,""ci95_low"":0.4,""ci95_high"":0.6,""n"":2}"\n',
        encoding="utf-8",
    )
    (directory / "raw.json").write_text("large tick payload must not be loaded", encoding="utf-8")

    response = TestClient(app).get("/experiments")

    assert response.status_code == 200
    [history] = response.json()
    assert history["run_id"] == run_id
    assert history["seeds"] == [17, 23]
    assert history["summaries"][0]["precision"]["mean"] == 0.5
    assert "time_series" not in history


@pytest.mark.parametrize(
    "seeds,scenarios,duration",
    [
        ([], ["oscillation"], 120),
        ([1, 1], ["oscillation"], 120),
        ([1], ["unknown"], 120),
        ([1], ["oscillation"], 119),
        ([1], ["oscillation"], 181),
    ],
)
def test_evaluation_rejects_unsafe_or_ambiguous_bounds(tmp_path, seeds, scenarios, duration):
    with pytest.raises(ValueError):
        run_evaluation(seeds, scenarios, duration, tmp_path)
