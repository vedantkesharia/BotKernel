import pytest

from botkernel.episode_metrics import score_episodes


def flags(duration, *intervals):
    return [any(start <= tick < stop for start, stop in intervals) for tick in range(duration)]


def test_half_open_boundaries_and_delays():
    result = score_episodes([(2, 6)], flags(12, (6, 8), (9, 10)))
    assert (result["episode_true_positives"], result["episode_false_positives"], result["episode_false_negatives"]) == (0, 2, 1)
    matched = score_episodes([(2, 6)], flags(12, (3, 8)))
    assert matched["episode_detection_delays_ticks"] == [1]
    assert matched["episode_clear_delays_ticks"] == [2]


def test_persistent_alarm_cannot_detect_two_episodes():
    result = score_episodes([(1, 3), (5, 7)], flags(10, (1, 8)))
    assert result["episode_true_positives"] == 1
    assert result["episode_false_negatives"] == 1
    assert result["episode_precision"] == 1
    assert result["episode_recall"] == 0.5


def test_early_alarm_censored_clear_and_empty_denominators():
    result = score_episodes([(3, 7)], flags(10, (1, 10)))
    assert result["episode_matches"][0]["alert_started_before_truth"]
    assert result["episode_detection_delays_ticks"] == [0]
    assert result["episode_clear_delays_ticks"] == [None]
    empty = score_episodes([], flags(10))
    assert empty["episode_precision"] is None and empty["episode_recall"] is None


def test_multiple_alerts_and_invalid_intervals():
    result = score_episodes([(1, 8)], flags(12, (2, 3), (4, 6)))
    assert result["episode_true_positives"] == 1
    assert result["episode_false_positives"] == 1
    assert result["alert_onsets_outside_truth"] == 0
    assert result["unmatched_alerts_overlapping_truth"] == 1
    with pytest.raises(ValueError):
        score_episodes([(1, 5), (4, 7)], flags(10))
