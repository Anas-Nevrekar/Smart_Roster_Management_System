export type RosterStatus = "draft" | "published";
export type AssignmentStatus = "working" | "weekly_off";

export interface RosterSummary {
  total_assignments: number;
  total_weekly_offs: number;
  total_requirements: number;
  requirements_satisfied: number;
  coverage_gaps: number;
  active_employees: number;
  active_brands: number;
  active_processes: number;
}

export interface ValidationAudit {
  requirements_total: number;
  requirements_satisfied: number;
  requirements_with_gaps: number;
  requirements_with_insufficient_available_staff: number;
  active_employees_checked: number;
  leave_conflicts: number;
  eligibility_conflicts: number;
  inactive_employee_conflicts: number;
  workable_day_conflicts: number;
  duplicate_assignments: number;
  weekly_off_overlaps: number;
  weekly_off_constraint_conflicts: number;
  invalid_requirement_assignments: number;
  weekly_off_count_errors: number;
}

export interface Diagnostic {
  code: string;
  message?: string;
  date?: string;
  employee_id?: string;
  brand_id?: string;
  process_id?: string;
  required_staffing?: number;
  actual_staffing?: number;
  available_staffing?: number;
  [field: string]: unknown;
}

export interface ValidationSummary {
  valid: boolean;
  errors: Diagnostic[];
  warnings?: Diagnostic[];
  summary?: RosterSummary;
  audit?: ValidationAudit;
  validated_at?: string;
}

export interface Roster {
  id: string;
  month: number;
  year: number;
  status: RosterStatus;
  generated_at: string;
  published_at: string | null;
  generated_by: string | null;
  published_by: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  assignment_count: number;
  weekly_off_count: number;
  summary: RosterSummary | Record<string, number> | null;
  latest_validation: ValidationSummary | null;
  master_data_stale?: boolean | null;
}

export interface RosterAssignment {
  id: string;
  roster_id: string;
  employee_id: string;
  employee_name: string | null;
  pod_id: string | null;
  pod_name: string | null;
  assignment_date: string;
  status: AssignmentStatus;
  brand_id: string | null;
  brand_name: string | null;
  process_id: string | null;
  process_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface GenerationAssignment {
  employee_id: string;
  date: string;
  brand_id: string;
  process_id: string;
  status: "assigned";
}

export interface WeeklyOff {
  employee_id: string;
  date: string;
  week_start: string;
  status: "weekly_off";
}

export interface CoverageRow {
  date: string;
  brand_id: string;
  brand_name: string;
  process_id: string;
  process_name: string;
  required_staffing: number | null;
  actual_staffing: number;
  staffing_gap: number;
  status: "satisfied" | "understaffed" | "not_operating";
}

export interface CoverageSummary {
  total_requirements: number;
  requirements_satisfied: number;
  coverage_gaps: number;
  total_working_assignments: number;
  total_weekly_offs: number;
}

export interface ValidationResult {
  success: true;
  roster_id: string;
  valid: boolean;
  errors: Diagnostic[];
  warnings: Diagnostic[];
  summary: RosterSummary;
  diagnostics: Diagnostic[];
  validated_at: string;
  version: number;
}

export interface GenerateRosterResult {
  success: boolean;
  month: number;
  year: number;
  roster?: Roster;
  summary: RosterSummary;
  assignments: GenerationAssignment[];
  weekly_offs: WeeklyOff[];
  validation: { is_valid: boolean; errors: Diagnostic[]; audit: ValidationAudit };
  diagnostics: Diagnostic[];
}
