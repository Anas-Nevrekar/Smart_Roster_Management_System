
from app.scheduling_engine.assignment import can_assign
from app.scheduling_engine.weekly_off import (
    initialize_weekly_off_state,
    assign_weekly_off
)
from app.scheduling_engine.sample_data_fixed import get_dataset

dataset = get_dataset("prototype")

state = {
    "roster": [],
    "daily_assignments": {}
}

weekly_off_state = initialize_weekly_off_state(
    dataset["employees"]
)

requirement = {
    "date": "2026-12-08",
    "brand_id": "B003",
    "process_id": "PR001",
    "required_staffing": 2
}

# Check before weekly off
print(
    "Before weekly off:",
    can_assign(dataset, state, "E003", requirement, weekly_off_state)
)

# Assign weekly off
assign_weekly_off(
    weekly_off_state,
    "E003",
    "2026-12-08"
)

# Check after weekly off
print(
    "After weekly off:",
    can_assign(dataset, state, "E003", requirement, weekly_off_state)
)

# Check another employee
print(
    "E004:",
    can_assign(dataset, state, "E004", requirement, weekly_off_state)
)
