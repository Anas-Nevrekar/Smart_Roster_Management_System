from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.entities import Weekday


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str
    assignment_date: date
    brand_id: str
    process_id: str


class AssignmentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str | None = None
    assignment_date: date | None = None
    brand_id: str | None = None
    process_id: str | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one assignment field must be supplied")
        return self


class AvailabilityImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change_type: Literal["availability"]
    employee_id: str
    workable_days: list[Weekday]
    weekly_off_per_week: int | None = Field(None, ge=0, le=7)


class TimeOffImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change_type: Literal["time_off"]
    employee_id: str
    time_off_type: Literal["planned_leave", "comp_off"]
    start_date: date
    end_date: date
    status: Literal["pending", "approved", "rejected"]
    reason: str | None = None
    time_off_id: str | None = None

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class EligibilityImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change_type: Literal["eligibility"]
    employee_id: str
    brand_id: str
    process_id: str
    is_active: bool


class OperatingRuleImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change_type: Literal["operating_rule"]
    brand_id: str
    process_id: str
    operating_days: list[Weekday]
    public_holiday_policy: Literal["operate", "closed"]
    minimum_staffing: int = Field(ge=0)
    coverage_overrides: list[dict] = Field(default_factory=list)
    is_active: bool = True


ImpactChange = Annotated[
    AvailabilityImpact | TimeOffImpact | EligibilityImpact | OperatingRuleImpact,
    Field(discriminator="change_type"),
]


class ChangeImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change: ImpactChange


class ChangeImpactResponse(BaseModel):
    valid: bool
    change_type: str
    roster_id: str
    current_version: int
    affected_dates: list[date]
    affected_employees: list[str]
    affected_brands: list[str]
    affected_processes: list[str]
    staffing_impact: list[dict]
    conflicts: list[dict]
    warnings: list[dict]
    summary: dict
