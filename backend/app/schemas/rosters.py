from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class GenerateRosterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    generated_by: str | None = None


class AssignmentOutput(BaseModel):
    employee_id: str
    date: str
    brand_id: str
    process_id: str
    status: Literal["assigned"]


class WeeklyOffOutput(BaseModel):
    employee_id: str
    date: str
    week_start: str
    status: Literal["weekly_off"]


class GenerationSummary(BaseModel):
    total_assignments: int
    total_weekly_offs: int
    total_requirements: int
    requirements_satisfied: int
    coverage_gaps: int
    active_employees: int
    active_brands: int
    active_processes: int


class GenerationValidation(BaseModel):
    is_valid: bool
    errors: list[dict[str, Any]]
    audit: dict[str, int]


class GenerateRosterResponse(BaseModel):
    success: bool
    month: int
    year: int
    summary: GenerationSummary
    assignments: list[AssignmentOutput]
    weekly_offs: list[WeeklyOffOutput]
    validation: GenerationValidation
    diagnostics: list[dict[str, Any]]
    roster: "RosterMetadata | None" = None


class RosterMetadata(BaseModel):
    id: str
    month: int
    year: int
    status: Literal["draft", "published"]
    generated_at: datetime
    published_at: datetime | None = None
    generated_by: str | None = None
    published_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int
    summary: dict[str, Any] | None = None
    assignment_count: int = 0
    weekly_off_count: int = 0
    latest_validation: dict[str, Any] | None = None
    master_data_stale: bool | None = None


class RosterAssignmentResponse(BaseModel):
    id: str
    roster_id: str
    employee_id: str
    employee_name: str | None = None
    pod_id: str | None = None
    pod_name: str | None = None
    assignment_date: date
    status: Literal["working", "weekly_off"]
    brand_id: str | None = None
    brand_name: str | None = None
    process_id: str | None = None
    process_name: str | None = None
    created_at: datetime
    updated_at: datetime


class RosterListResponse(BaseModel):
    success: bool = True
    data: list[RosterMetadata]
    total: int


class RosterResponse(BaseModel):
    success: bool = True
    data: RosterMetadata


class RosterAssignmentsResponse(BaseModel):
    success: bool = True
    data: list[RosterAssignmentResponse]
    total: int


class CoverageRow(BaseModel):
    date: date
    brand_id: str
    brand_name: str
    process_id: str
    process_name: str
    required_staffing: int | None
    actual_staffing: int
    staffing_gap: int
    status: Literal["satisfied", "understaffed", "not_operating"]


class CoverageSummary(BaseModel):
    total_requirements: int
    requirements_satisfied: int
    coverage_gaps: int
    total_working_assignments: int
    total_weekly_offs: int


class CoverageResponse(BaseModel):
    success: bool = True
    data: list[CoverageRow]
    summary: CoverageSummary


class ValidateRosterResponse(BaseModel):
    success: bool = True
    roster_id: str
    valid: bool
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    summary: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    validated_at: datetime
    version: int


class PublishRosterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published_by: str | None = None
