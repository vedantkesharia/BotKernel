from botkernel.effect_relationships import is_contiguous_reversal
from botkernel.investigator import correlate


def effect(action, version, agent, before, after):
    return {"action_id": action, "version": version, "agent": agent, "resource": "r",
            "before_capacity": before, "after_capacity": after}


def test_reversal_requires_version_capacity_and_resource_continuity():
    first = effect("a", 1, "cost", 4, 3)
    second = effect("b", 2, "performance", 3, 4)
    assert is_contiguous_reversal(first, second)
    assert not is_contiguous_reversal(first, {**second, "version": 3})
    assert not is_contiguous_reversal(first, {**second, "before_capacity": 2})
    assert not is_contiguous_reversal(first, {**second, "resource": "other"})
    assert not is_contiguous_reversal(second, first)


def test_investigator_does_not_infer_across_capacity_discontinuity():
    first = effect("a", 1, "cost", 4, 3)
    second = effect("b", 2, "performance", 2, 4)
    result = correlate({"effects": [first, second]})
    assert result["reversals"] == []
    assert result["warnings"] == ["Effect history has a version or capacity gap"]
