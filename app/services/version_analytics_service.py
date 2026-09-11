"""
Entity Version Analytics & Diff Inspection Service for BankVCS 2.0.
Provides pure Python analytics for version history curves, snapshot distributions,
field-level change metrics, and maker-checker rollback SLA analytics.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any

from app import db
from app.models.version import EntityVersion
from app.models.workflow_risk import RollbackRequest, RollbackStatus
from app.utils import diff as diff_util

logger = logging.getLogger(__name__)


def generate_version_analytics_summary() -> Dict[str, Any]:
    """
    Generates system-wide analytics for entity database versioning activity,
    snapshot distribution across entities, and rollback operation statistics.
    """
    total_versions = EntityVersion.query.count()

    type_counts = {}
    versions = EntityVersion.query.all()
    
    for v in versions:
        et = v.entity_type or "UNKNOWN"
        type_counts[et] = type_counts.get(et, 0) + 1

    change_types = {}
    for v in versions:
        ct = v.change_type or "UPDATE"
        change_types[ct] = change_types.get(ct, 0) + 1

    rollbacks = RollbackRequest.query.all()
    rollback_status_counts = {}
    for r in rollbacks:
        st = r.status.value if hasattr(r.status, "value") else str(r.status)
        rollback_status_counts[st] = rollback_status_counts.get(st, 0) + 1

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_snapshots_recorded": total_versions,
        "snapshot_distribution_by_entity": type_counts,
        "snapshot_distribution_by_change_type": change_types,
        "rollback_requests": {
            "total_requests": len(rollbacks),
            "status_breakdown": rollback_status_counts
        },
        "recent_version_snapshots": [v.to_dict() for v in EntityVersion.query.order_by(EntityVersion.created_at.desc()).limit(15)]
    }


def analyze_entity_version_trajectory(entity_type: str, entity_id: int) -> Dict[str, Any]:
    """
    Analyzes the complete version history trajectory for a specific entity ID.
    Calculates field change frequencies and computes consecutive diffs.
    """
    versions = EntityVersion.query.filter_by(
        entity_type=entity_type.upper(),
        entity_id=entity_id
    ).order_by(EntityVersion.version_number.asc()).all()

    if not versions:
        return {
            "entity_type": entity_type.upper(),
            "entity_id": entity_id,
            "version_count": 0,
            "trajectory": []
        }

    trajectory = []
    field_modification_counts: Dict[str, int] = {}

    for i, v in enumerate(versions):
        step_info = {
            "version_number": v.version_number,
            "change_type": v.change_type,
            "change_summary": v.change_summary,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "changed_by": v.changed_by,
        }

        if i > 0:
            prev_snapshot = versions[i - 1].new_data or {}
            curr_snapshot = v.new_data or {}
            diff_result = diff_util.compute_dict_diff(prev_snapshot, curr_snapshot)
            step_info["diff_analysis"] = diff_result

            for mod in diff_result.get("modified", []):
                field = mod["field"]
                field_modification_counts[field] = field_modification_counts.get(field, 0) + 1

        trajectory.append(step_info)

    return {
        "entity_type": entity_type.upper(),
        "entity_id": entity_id,
        "version_count": len(versions),
        "latest_version": versions[-1].version_number,
        "most_frequently_modified_fields": field_modification_counts,
        "trajectory": trajectory
    }
