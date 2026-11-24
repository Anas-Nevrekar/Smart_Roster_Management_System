"""
Smart Roster Management System — Python engine sample data

This file uses plain string IDs and ISO date strings so the scheduling engine
can run without MongoDB. Convert these IDs to MongoDB ObjectIds when you
integrate the data with the application database.

Two scenarios are provided:
    VALID_DATA    -> a roster should be feasible
    CONFLICT_DATA -> Brand C / Customer Support has no available eligible
                     employees on 2026-12-08, so coverage should fail

Prototype assumptions:
- 10 employees, 2 pods, 3 brands, 3 processes.
- Each employee has one weekly off; Sunday is the off day in this fixture.
- Employees can work Monday through Saturday.
- One employee can handle multiple processes on the same day.
- A working assignment is one employee + one brand + one process + one date.
"""

from copy import deepcopy


DAYS_MON_SAT = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday",
]

ALL_DAYS = DAYS_MON_SAT + ["Sunday"]


VALID_DATA = {
    "employees": [
        {
            "employee_id": "E001",
            "name": "Rahul Sharma",
            "email": "rahul@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E002",
            "name": "Aman Khan",
            "email": "aman@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E003",
            "name": "Priya Patel",
            "email": "priya@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E004",
            "name": "Rohan Mehta",
            "email": "rohan@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E005",
            "name": "Sara Shaikh",
            "email": "sara@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E006",
            "name": "Karan Desai",
            "email": "karan@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E007",
            "name": "Neha Joshi",
            "email": "neha@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E008",
            "name": "Imran Ali",
            "email": "imran@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E009",
            "name": "Ayesha Khan",
            "email": "ayesha@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
        {
            "employee_id": "E010",
            "name": "Vikram Rao",
            "email": "vikram@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": DAYS_MON_SAT.copy(),
        },
    ],

    "pods": [
        {
            "pod_id": "POD01",
            "pod_name": "Pod Alpha",
            "pod_lead_id": "E001",
            "description": "Primary operations pod",
            "is_active": True,
        },
        {
            "pod_id": "POD02",
            "pod_name": "Pod Beta",
            "pod_lead_id": "E006",
            "description": "Secondary operations pod",
            "is_active": True,
        },
    ],

    "brands": [
        {
            "brand_id": "B001",
            "brand_name": "Northstar",
            "description": "Single-resource brand: Rahul handles all its processes",
            "is_active": True,
        },
        {
            "brand_id": "B002",
            "brand_name": "UrbanNest",
            "description": "Single-resource brand: Aman handles all its processes",
            "is_active": True,
        },
        {
            "brand_id": "B003",
            "brand_name": "PureGlow",
            "description": "Multi-resource brand used to test shared process coverage",
            "is_active": True,
        },
    ],

    "processes": [
        {
            "process_id": "PR001",
            "process_name": "Customer Support",
            "description": "Handles customer queries and support",
            "is_active": True,
        },
        {
            "process_id": "PR002",
            "process_name": "ACC",
            "description": "Handles abandoned cart conversions",
            "is_active": True,
        },
        {
            "process_id": "PR003",
            "process_name": "Retention",
            "description": "Handles customer retention activities",
            "is_active": True,
        },
    ],

    # Eligibility only. These are not actual daily roster assignments.
    "employee_assignments": [
        # Northstar: one employee handles all three processes.
        {"employee_id": "E001", "brand_id": "B001", "process_id": "PR001", "is_active": True},
        {"employee_id": "E001", "brand_id": "B001", "process_id": "PR002", "is_active": True},
        {"employee_id": "E001", "brand_id": "B001", "process_id": "PR003", "is_active": True},

        # UrbanNest: one employee handles all three processes.
        {"employee_id": "E002", "brand_id": "B002", "process_id": "PR001", "is_active": True},
        {"employee_id": "E002", "brand_id": "B002", "process_id": "PR002", "is_active": True},
        {"employee_id": "E002", "brand_id": "B002", "process_id": "PR003", "is_active": True},

        # PureGlow: multiple employees share Customer Support.
        {"employee_id": "E003", "brand_id": "B003", "process_id": "PR001", "is_active": True},
        {"employee_id": "E004", "brand_id": "B003", "process_id": "PR001", "is_active": True},
        {"employee_id": "E005", "brand_id": "B003", "process_id": "PR001", "is_active": True},

        # PureGlow: multiple employees share ACC.
        {"employee_id": "E006", "brand_id": "B003", "process_id": "PR002", "is_active": True},
        {"employee_id": "E007", "brand_id": "B003", "process_id": "PR002", "is_active": True},

        # PureGlow: multiple employees share Retention.
        {"employee_id": "E008", "brand_id": "B003", "process_id": "PR003", "is_active": True},
        {"employee_id": "E009", "brand_id": "B003", "process_id": "PR003", "is_active": True},
        {"employee_id": "E010", "brand_id": "B003", "process_id": "PR003", "is_active": True},
    ],

    "brand_process_rules": [
        # Northstar: all processes run Monday-Saturday and operate on public holidays.
        {
            "brand_id": "B001",
            "process_id": "PR001",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "operate",
            "minimum_staffing": 1,
            "coverage_overrides": [],
            "is_active": True,
        },
        {
            "brand_id": "B001",
            "process_id": "PR002",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "operate",
            "minimum_staffing": 1,
            "coverage_overrides": [],
            "is_active": True,
        },
        {
            "brand_id": "B001",
            "process_id": "PR003",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "operate",
            "minimum_staffing": 1,
            "coverage_overrides": [],
            "is_active": True,
        },

        # UrbanNest: all processes are closed on public holidays.
        {
            "brand_id": "B002",
            "process_id": "PR001",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "closed",
            "minimum_staffing": 1,
            "coverage_overrides": [],
            "is_active": True,
        },
        {
            "brand_id": "B002",
            "process_id": "PR002",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "closed",
            "minimum_staffing": 1,
            "coverage_overrides": [],
            "is_active": True,
        },
        {
            "brand_id": "B002",
            "process_id": "PR003",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "closed",
            "minimum_staffing": 1,
            "coverage_overrides": [],
            "is_active": True,
        },

        # PureGlow: different minimum staffing and holiday policies per process.
        {
            "brand_id": "B003",
            "process_id": "PR001",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "operate",
            "minimum_staffing": 2,
            "coverage_overrides": [],
            "is_active": True,
        },
        {
            "brand_id": "B003",
            "process_id": "PR002",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "closed",
            "minimum_staffing": 1,
            "coverage_overrides": [],
            "is_active": True,
        },
        {
            "brand_id": "B003",
            "process_id": "PR003",
            "operating_days": DAYS_MON_SAT.copy(),
            "public_holiday_policy": "operate",
            "minimum_staffing": 1,
            "coverage_overrides": [],
            "is_active": True,
        },
    ],

    "employee_time_off": [],

    "public_holidays": [
        {
            "holiday_id": "H001",
            "holiday_name": "Christmas",
            "holiday_date": "2026-12-25",
        },
    ],

    # Roster and roster_assignments are outputs of the engine, so start empty.
    "rosters": [],
    "roster_assignments": [],
}


# This scenario copies the valid configuration, then makes all three eligible
# PureGlow Customer Support employees unavailable on the same required day.
CONFLICT_DATA = deepcopy(VALID_DATA)
CONFLICT_DATA["employee_time_off"] = [
    {
        "time_off_id": "TO001",
        "employee_id": "E003",
        "time_off_type": "planned_leave",
        "start_date": "2026-12-08",
        "end_date": "2026-12-08",
        "status": "approved",
        "reason": "Conflict test: approved leave",
        "approved_by": "E006",
    },
    {
        "time_off_id": "TO002",
        "employee_id": "E004",
        "time_off_type": "planned_leave",
        "start_date": "2026-12-08",
        "end_date": "2026-12-08",
        "status": "approved",
        "reason": "Conflict test: approved leave",
        "approved_by": "E006",
    },
    {
        "time_off_id": "TO003",
        "employee_id": "E005",
        "time_off_type": "planned_leave",
        "start_date": "2026-12-08",
        "end_date": "2026-12-08",
        "status": "approved",
        "reason": "Conflict test: approved leave",
        "approved_by": "E006",
    },
]


def get_dataset(scenario="valid"):
    """Return an independent copy of the requested test dataset."""
    if scenario == "valid":
        return deepcopy(VALID_DATA)
    if scenario == "conflict":
        return deepcopy(CONFLICT_DATA)
    raise ValueError("scenario must be either 'valid' or 'conflict'")


if __name__ == "__main__":
    valid = get_dataset("valid")
    conflict = get_dataset("conflict")

    print("Valid dataset:")
    print(f"  Employees: {len(valid['employees'])}")
    print(f"  Brands: {len(valid['brands'])}")
    print(f"  Employee eligibility records: {len(valid['employee_assignments'])}")

    print("\nConflict dataset:")
    print(f"  Approved time-off records: {len(conflict['employee_time_off'])}")
    print("  Expected issue: PureGlow Customer Support has zero available")
    print("  eligible employees on 2026-12-08 (minimum staffing is 2).")
