"""Idempotent MongoDB indexes used by the repository."""

INDEXES: dict[str, list[dict]] = {
    "employees": [
        {"keys": [("employee_id", 1)], "unique": True, "name": "uq_employee_domain_id"},
        {"keys": [("email", 1)], "unique": True, "name": "uq_employees_email"},
        {"keys": [("pod_id", 1)], "name": "ix_employees_pod"},
    ],
    "pods": [
        {"keys": [("pod_name", 1)], "unique": True, "name": "uq_pods_name"},
    ],
    "brands": [
        {"keys": [("brand_name", 1)], "unique": True, "name": "uq_brands_name"},
    ],
    "processes": [
        {"keys": [("process_name", 1)], "unique": True, "name": "uq_processes_name"},
    ],
    "employee_assignments": [
        {"keys": [("employee_id", 1), ("brand_id", 1), ("process_id", 1)], "unique": True, "name": "uq_employee_brand_process"},
    ],
    "brand_process_rules": [
        {"keys": [("brand_id", 1), ("process_id", 1)], "unique": True, "name": "uq_brand_process_rule"},
    ],
    "employee_time_off": [
        {"keys": [("employee_id", 1), ("start_date", 1), ("end_date", 1)], "name": "ix_time_off_employee_range"},
    ],
    "public_holidays": [{"keys": [("holiday_date", 1)], "unique": True, "name": "uq_public_holiday_date"}],
    "rosters": [
        {"keys": [("month", 1), ("year", 1)], "unique": True, "name": "uq_roster_month_year"},
        {"keys": [("status", 1), ("year", -1), ("month", -1)], "name": "ix_roster_status_date"},
    ],
    "roster_assignments": [
        {
            "keys": [("roster_id", 1), ("employee_id", 1), ("assignment_date", 1), ("brand_id", 1), ("process_id", 1)],
            "unique": True, "name": "uq_assignment_employee_date_pair",
            "partialFilterExpression": {"status": "working"},
        },
        {
            "keys": [("roster_id", 1), ("employee_id", 1), ("assignment_date", 1)],
            "unique": True, "name": "uq_weekly_off_employee_date",
            "partialFilterExpression": {"status": "weekly_off"},
        },
        {"keys": [("roster_id", 1), ("brand_id", 1), ("process_id", 1), ("assignment_date", 1)], "name": "ix_assignment_coverage"},
    ],
}


def ensure_indexes(database) -> None:
    """Create each index idempotently; constraint failures are surfaced to readiness."""
    for collection_name, definitions in INDEXES.items():
        collection = database[collection_name]
        for definition in definitions:
            spec = dict(definition)
            keys = spec.pop("keys")
            try:
                collection.create_index(keys, **spec)
            except Exception as exc:
                if spec.get("unique") and (type(exc).__name__ == "DuplicateKeyError" or getattr(exc, "code", None) == 11000):
                    fields = ", ".join(field for field, _direction in keys)
                    details = getattr(exc, "details", None) or {}
                    conflicting_values = details.get("keyValue")
                    value_note = f" Conflicting key values: {conflicting_values}." if conflicting_values else ""
                    raise RuntimeError(
                        f"Cannot create unique index {spec['name']} on {collection_name}; existing records duplicate {fields}. "
                        f"{value_note} Reconcile those records and retry; no data was removed."
                    ) from None
                raise
