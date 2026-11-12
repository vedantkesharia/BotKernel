"""Episode-level scoring for scheduled half-open intervals in virtual time."""


def score_episodes(harmful_intervals, alarm_active):
    duration = len(alarm_active)
    previous_stop = 0
    for start, stop in harmful_intervals:
        if not (previous_stop <= start < stop <= duration):
            raise ValueError("Ground-truth intervals must be sorted, disjoint and within the run")
        previous_stop = stop

    alerts = []
    start = None
    for tick, active in enumerate(alarm_active):
        if active and start is None:
            start = tick
        elif not active and start is not None:
            alerts.append({"start": start, "stop": tick, "clear_observed": True})
            start = None
    if start is not None:
        alerts.append({"start": start, "stop": duration, "clear_observed": False})

    matches = []
    used = set()
    for truth_index, (truth_start, truth_stop) in enumerate(harmful_intervals):
        for alert_index, alert in enumerate(alerts):
            if alert_index not in used and alert["start"] < truth_stop and truth_start < alert["stop"]:
                used.add(alert_index)
                matches.append({
                    "truth_index": truth_index,
                    "alert_index": alert_index,
                    "detection_delay_ticks": max(0, alert["start"] - truth_start),
                    "alert_clear_delay_ticks": (
                        max(0, alert["stop"] - truth_stop) if alert["clear_observed"] else None
                    ),
                    "alert_started_before_truth": alert["start"] < truth_start,
                })
                break

    tp = len(matches)
    fp = len(alerts) - tp
    fn = len(harmful_intervals) - tp
    return {
        "episode_true_positives": tp,
        "episode_false_positives": fp,
        "episode_false_negatives": fn,
        "episode_precision": tp / (tp + fp) if tp + fp else None,
        "episode_recall": tp / (tp + fn) if tp + fn else None,
        "alert_onsets_outside_truth": sum(
            not any(start <= alert["start"] < stop for start, stop in harmful_intervals)
            for alert in alerts
        ),
        "unmatched_alerts_overlapping_truth": sum(
            index not in used and any(alert["start"] < stop and start < alert["stop"]
                                      for start, stop in harmful_intervals)
            for index, alert in enumerate(alerts)
        ),
        "alert_episodes": alerts,
        "episode_matches": matches,
        "episode_detection_delays_ticks": [item["detection_delay_ticks"] for item in matches],
        "episode_clear_delays_ticks": [item["alert_clear_delay_ticks"] for item in matches],
    }
