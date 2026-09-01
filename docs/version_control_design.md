# Version Control Design

See `app/services/version_service.py`.

- `create_version(entity_type, entity_id, change_type, old_data, new_data,
  changed_by, ...)` — writes one version row + one audit log row.
- `get_history(entity_type, entity_id)` — full ordered history for a record.
- `diff_versions(entity_type, entity_id, v1, v2)` — field-level diff,
  classifying each field as added / removed / modified / unchanged.
- `restore_version(entity_type, entity_id, version_number, changed_by,
  apply_fn)` — restores non-financial entities only; raises an error if
  called with `entity_type == TRANSACTION`.

Version numbers are per-entity and monotonically increasing, computed as
`max(existing version_number) + 1`.
