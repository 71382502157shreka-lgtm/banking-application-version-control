"""
Pure Python Field-Level Diff Module for Entity Version Comparisons.
Computes field-level differences between old_data and new_data JSON snapshots.
"""

from typing import Dict, Any


def compute_field_diff(old_data: Dict[str, Any] | None, new_data: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Compare old_data and new_data dictionaries and return structured diff information.
    Categories: 'modified', 'added', 'removed', 'unchanged'
    """
    old_data = old_data or {}
    new_data = new_data or {}

    all_keys = sorted(set(old_data.keys()) | set(new_data.keys()))
    diff_result = {}

    for key in all_keys:
        in_old = key in old_data
        in_new = key in new_data

        val_old = old_data.get(key)
        val_new = new_data.get(key)

        if in_old and in_new:
            if val_old == val_new:
                diff_result[key] = {"status": "unchanged", "old": val_old, "new": val_new}
            else:
                diff_result[key] = {"status": "modified", "old": val_old, "new": val_new}
        elif in_new:
            diff_result[key] = {"status": "added", "old": None, "new": val_new}
        elif in_old:
            diff_result[key] = {"status": "removed", "old": val_old, "new": None}

    return diff_result
