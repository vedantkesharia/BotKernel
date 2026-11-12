"""Relationships that require contiguous committed resource history."""


def is_contiguous_reversal(before, after):
    return (
        before["resource"] == after["resource"]
        and after["version"] == before["version"] + 1
        and before["after_capacity"] == after["before_capacity"]
        and before["agent"] != after["agent"]
        and (before["after_capacity"] - before["before_capacity"])
        * (after["after_capacity"] - after["before_capacity"]) < 0
    )
