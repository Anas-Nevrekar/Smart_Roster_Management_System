from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

Weekday = Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmployeeCreate(InputModel):
    employee_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    email: EmailStr
    pod_id: str | None = None
    is_active: bool = True
    weekly_off_per_week: int = Field(default=1, ge=0, le=7)
    workable_days: list[Weekday] = Field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])


class EmployeeUpdate(EmployeeCreate):
    pass


class EmployeeStatus(InputModel):
    is_active: bool


class PodCreate(InputModel):
    pod_name: str = Field(min_length=1)
    pod_lead_id: str | None = None
    description: str | None = None
    is_active: bool = True


class PodUpdate(PodCreate):
    pass


class PodLead(InputModel):
    pod_lead_id: str | None


class Membership(InputModel):
    employee_ids: list[str]


class BrandCreate(InputModel):
    brand_name: str = Field(min_length=1)
    description: str | None = None
    is_active: bool = True


class BrandUpdate(BrandCreate):
    pass


class ProcessCreate(InputModel):
    process_name: str = Field(min_length=1)
    description: str | None = None
    is_active: bool = True


class ProcessUpdate(ProcessCreate):
    pass


class EligibilityItem(InputModel):
    brand_id: str
    process_id: str
    is_active: bool = True


class EligibilityCreate(EligibilityItem):
    employee_id: str


class EligibilityUpdate(InputModel):
    employee_id: str
    brand_id: str
    process_id: str
    is_active: bool = True


class EligibilityReplacement(InputModel):
    items: list[EligibilityItem]


class CoverageOverride(InputModel):
    date: date
    minimum_staffing: int = Field(ge=0)


class OperatingRuleCreate(InputModel):
    brand_id: str
    process_id: str
    operating_days: list[Weekday]
    public_holiday_policy: Literal["operate", "closed"]
    minimum_staffing: int = Field(ge=0)
    coverage_overrides: list[CoverageOverride] = Field(default_factory=list)
    is_active: bool = True


class OperatingRuleUpdate(OperatingRuleCreate):
    pass


class TimeOffCreate(InputModel):
    employee_id: str
    time_off_type: Literal["planned_leave", "comp_off"]
    start_date: date
    end_date: date
    status: Literal["pending", "approved", "rejected"] = "pending"
    reason: str | None = None
    approved_by: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class TimeOffUpdate(TimeOffCreate):
    pass


class PublicHolidayCreate(InputModel):
    holiday_name: str = Field(min_length=1)
    holiday_date: date
    description: str | None = None


class PublicHolidayUpdate(PublicHolidayCreate):
    pass


class AvailabilityUpdate(InputModel):
    workable_days: list[Weekday]
    weekly_off_per_week: int = Field(ge=0, le=7)
