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
- The original prototype fixture has 10 employees, 2 pods, 3 brands, 3 processes.
- The assessment fixture has 32 employees (31 active), 5 pods, 25 brands, 3 processes.
- Each employee has one weekly off; the engine chooses the day based on coverage.
- Employees are eligible to work any day of the week unless time off applies.
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
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E002",
            "name": "Aman Khan",
            "email": "aman@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E003",
            "name": "Priya Patel",
            "email": "priya@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E004",
            "name": "Rohan Mehta",
            "email": "rohan@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E005",
            "name": "Sara Shaikh",
            "email": "sara@example.com",
            "pod_id": "POD01",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E006",
            "name": "Karan Desai",
            "email": "karan@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E007",
            "name": "Neha Joshi",
            "email": "neha@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E008",
            "name": "Imran Ali",
            "email": "imran@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E009",
            "name": "Ayesha Khan",
            "email": "ayesha@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
        },
        {
            "employee_id": "E010",
            "name": "Vikram Rao",
            "email": "vikram@example.com",
            "pod_id": "POD02",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": ALL_DAYS.copy()
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


def _build_assessment_data():
    """Build the larger assessment fixture while keeping IDs deterministic."""
    data = deepcopy(VALID_DATA)
    data["employees"] = []
    data["pods"] = []
    data["brands"] = []
    data["employee_assignments"] = []
    data["brand_process_rules"] = []

    existing_names = [
        "Rahul Sharma", "Aman Khan", "Priya Patel", "Rohan Mehta",
        "Sara Shaikh", "Karan Desai", "Neha Joshi", "Imran Ali",
        "Ayesha Khan", "Vikram Rao",
    ]
    additional_names = [
        "Ananya Iyer", "Kabir Malhotra", "Meera Nair", "Arjun Reddy",
        "Zoya Merchant", "Dev Kulkarni", "Ishita Bose", "Aditya Menon",
        "Nisha Kapoor", "Rehan Siddiqui", "Tara Deshmukh", "Vivaan Shah",
        "Sana Fernandes", "Aarav Chawla", "Diya Krishnan", "Farhan Qureshi",
        "Maya Banerjee", "Rishi Sethi", "Leena Thomas", "Neil Dutta",
        "Aisha Bhat", "Omar Desai",
    ]
    names = existing_names + additional_names

    # Five pods of six or seven people; each lead is a member of that pod.
    pod_starts = [0, 7, 14, 20, 26]
    pod_ends = pod_starts[1:] + [len(names)]
    for pod_number, (start, end) in enumerate(zip(pod_starts, pod_ends), start=1):
        pod_id = f"POD{pod_number:02d}"
        data["pods"].append({
            "pod_id": pod_id,
            "pod_name": f"Operations Pod {pod_number}",
            "pod_lead_id": f"E{start + 1:03d}",
            "description": f"Roster operations team {pod_number}",
            "is_active": True,
        })
        for index in range(start, end):
            number = index + 1
            data["employees"].append({
                "employee_id": f"E{number:03d}",
                "name": names[index],
                "email": f"employee{number:03d}@example.com",
                "pod_id": pod_id,
                "is_active": number != 32,
                "weekly_off_per_week": 1,
                "workable_days": ALL_DAYS.copy(),
            })

    processes = data["processes"]
    process_ids = [p["process_id"] for p in processes]
    brand_names = {
        "B001": ("Northstar", "Dedicated brand"),
        "B002": ("UrbanNest", "Dedicated brand"),
        "B003": ("PureGlow", "Shared team with cross-process coverage"),
    }
    for number in range(4, 22):
        brand_id = f"B{number:03d}"
        brand_names[brand_id] = (f"BrightCart {number - 3}", "Dedicated brand")
    for number in range(22, 26):
        brand_id = f"B{number:03d}"
        brand_names[brand_id] = (f"MarketLane {number - 21}", "Shared team")

    data["brands"] = [{
        "brand_id": brand_id,
        "brand_name": details[0],
        "description": details[1],
        "is_active": True,
    } for brand_id, details in brand_names.items()]

    # 20 brands have one employee covering all three processes (80% of 25).
    dedicated_employee_by_brand = {"B001": "E001", "B002": "E002"}
    for employee_number, brand_number in zip(range(3, 21), range(4, 22)):
        dedicated_employee_by_brand[f"B{brand_number:03d}"] = f"E{employee_number:03d}"
    for brand_id, employee_id in dedicated_employee_by_brand.items():
        for process_id in process_ids:
            data["employee_assignments"].append({
                "employee_id": employee_id, "brand_id": brand_id,
                "process_id": process_id, "is_active": True,
            })

    # PureGlow has three shared employees, with overlapping but distinct
    # process coverage. Each of the other shared brands has a two-person team.
    shared_members = {
        "B003": ["E021", "E022", "E023"],
        "B022": ["E024", "E025"],
        "B023": ["E026", "E027"],
        "B024": ["E028", "E029"],
        "B025": ["E030", "E031"],
    }
    shared_process_members = {
        "B003": {
            "PR001": ["E021", "E022", "E023"],
            "PR002": ["E021", "E022"],
            "PR003": ["E022", "E023"],
        },
    }
    for brand_id, members in shared_members.items():
        process_map = shared_process_members.get(brand_id, {
            process_id: members for process_id in process_ids
        })
        for process_id, employee_ids in process_map.items():
            for employee_id in employee_ids:
                data["employee_assignments"].append({
                    "employee_id": employee_id, "brand_id": brand_id,
                    "process_id": process_id, "is_active": True,
                })

    # Preserve an inactive former employee's historical, disabled eligibility.
    for process_id in process_ids:
        data["employee_assignments"].append({
            "employee_id": "E032", "brand_id": "B025",
            "process_id": process_id, "is_active": False,
        })

    # Preserve differentiated operating and holiday policies. Shared daily
    # brands have both employees eligible for every process to cover weekly offs.
    for brand_id in dedicated_employee_by_brand:
        for process_index, process_id in enumerate(process_ids):
            data["brand_process_rules"].append({
                "brand_id": brand_id,
                "process_id": process_id,
                "operating_days": DAYS_MON_SAT.copy(),
                "public_holiday_policy": "operate" if process_index == 0 else "closed",
                "minimum_staffing": 1,
                "coverage_overrides": [],
                "is_active": True,
            })

    for brand_id in shared_members:
        if brand_id == "B003":
            operating_days = DAYS_MON_SAT.copy()
            holiday_policies = {"PR001": "operate", "PR002": "closed", "PR003": "operate"}
        elif brand_id == "B022":
            operating_days = ALL_DAYS.copy()
            holiday_policies = {process_id: "operate" for process_id in process_ids}
        elif brand_id == "B023":
            operating_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            holiday_policies = {process_id: "closed" for process_id in process_ids}
        elif brand_id == "B024":
            operating_days = DAYS_MON_SAT.copy()
            holiday_policies = {process_id: "operate" for process_id in process_ids}
        else:  # B025: all seven days, with public holidays closed.
            operating_days = ALL_DAYS.copy()
            holiday_policies = {process_id: "closed" for process_id in process_ids}

        for process_id in process_ids:
            data["brand_process_rules"].append({
                "brand_id": brand_id,
                "process_id": process_id,
                "operating_days": operating_days.copy(),
                "public_holiday_policy": holiday_policies[process_id],
                "minimum_staffing": 2 if brand_id == "B003" and process_id == "PR001" else 1,
                "coverage_overrides": [],
                "is_active": True,
            })

    data["employee_time_off"] = [
        {
            "time_off_id": "ATO001", "employee_id": "E021",
            "time_off_type": "planned_leave", "start_date": "2026-12-09",
            "end_date": "2026-12-09", "status": "approved",
            "reason": "Approved personal leave", "approved_by": "E001",
        },
        {
            "time_off_id": "ATO002", "employee_id": "E024",
            "time_off_type": "comp_off", "start_date": "2026-12-15",
            "end_date": "2026-12-15", "status": "pending",
            "reason": "Pending comp-off request",
        },
    ]
    return data


PROTOTYPE_DATA = VALID_DATA
PROTOTYPE_CONFLICT_DATA = CONFLICT_DATA
ASSESSMENT_DATA = _build_assessment_data()
ASSESSMENT_CONFLICT_DATA = deepcopy(ASSESSMENT_DATA)
ASSESSMENT_CONFLICT_DATA["employee_time_off"].extend([
    {
        "time_off_id": f"ACTO00{number}",
        "employee_id": f"E{number + 20:03d}",
        "time_off_type": "planned_leave",
        "start_date": "2026-12-08",
        "end_date": "2026-12-08",
        "status": "approved",
        "reason": "Conflict test: approved leave",
        "approved_by": "E001",
    }
    for number in range(1, 4)
])

# Public VALID_DATA/CONFLICT_DATA now represent the assessment-sized fixture;
# the original 10-employee scenarios remain available as PROTOTYPE_DATA.
VALID_DATA = ASSESSMENT_DATA
CONFLICT_DATA = ASSESSMENT_CONFLICT_DATA


def get_dataset(scenario="valid"):
    """Return an independent copy of an assessment or prototype scenario."""
    scenarios = {
        "valid": ASSESSMENT_DATA,
        "assessment": ASSESSMENT_DATA,
        "assessment_valid": ASSESSMENT_DATA,
        "conflict": ASSESSMENT_CONFLICT_DATA,
        "assessment_conflict": ASSESSMENT_CONFLICT_DATA,
        "prototype": PROTOTYPE_DATA,
        "prototype_valid": PROTOTYPE_DATA,
        "prototype_conflict": PROTOTYPE_CONFLICT_DATA,
    }
    if scenario not in scenarios:
        raise ValueError(
            "scenario must be valid, conflict, assessment, or a prototype variant"
        )
    return deepcopy(scenarios[scenario])


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
