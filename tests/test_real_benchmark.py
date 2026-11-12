import httpx

from botkernel.real_benchmark import _request, percentile


def test_percentiles_interpolate_and_handle_empty_samples():
    assert percentile([], 95) is None
    assert percentile([30, 10, 20], 50) == 20
    assert percentile([10, 20], 95) == 19.5


def test_request_observes_committed_terminal_state():
    def handle(request):
        if request.method == "POST":
            return httpx.Response(202, json={"id": "action-1"})
        return httpx.Response(200, json={"state": "SUCCEEDED"})

    with httpx.Client(base_url="http://benchmark", transport=httpx.MockTransport(handle)) as client:
        row = _request(client, "agent", "resource", 0, 2, "run", "key")
    assert row["action_id"] == "action-1"
    assert row["state"] == "SUCCEEDED"
    assert row["completion_ms"] >= row["admission_ms"] >= 0


def test_rejected_action_has_no_completion_or_action_id():
    with httpx.Client(
        base_url="http://benchmark",
        transport=httpx.MockTransport(lambda request: httpx.Response(409, text="conflict")),
    ) as client:
        row = _request(client, "agent", "resource", 0, 2, "run", "key")
    assert row["state"] == "REJECTED"
    assert row["action_id"] is None
    assert row["completion_ms"] is None
