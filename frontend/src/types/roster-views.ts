import type { Employee, Pod, Brand, Process } from "./master-data";
import type { Roster, RosterAssignment } from "./roster";
export interface CompanyRosterView { view: "company"; roster: Roster; assignments: RosterAssignment[]; weekly_offs: RosterAssignment[]; employee_groups?: EmployeeRosterGroup[] }
export interface EmployeeRosterGroup { employee_id: string; employee_name: string | null; pod_id: string | null; pod_name: string | null; assignments: RosterAssignment[]; weekly_offs: RosterAssignment[] }
export interface EmployeeRosterView { view: "employee"; roster: Roster; employees: EmployeeRosterGroup[] }
export interface PodRosterGroup { pod: Pod | { pod_id: string; pod_name: string; pod_lead_id: string | null }; pod_lead: Employee | null; employees: EmployeeRosterGroup[] }
export interface PodRosterView { view: "pod"; roster: Roster; pods: PodRosterGroup[] }
export interface BrandProcessAssignments { process: Process | { process_id: string; process_name: string | null }; assignments: RosterAssignment[]; weekly_offs?: RosterAssignment[] }
export interface BrandRosterGroup { brand: Brand | { brand_id: string; brand_name: string | null }; processes: BrandProcessAssignments[] }
export interface BrandRosterView { view: "brand"; roster: Roster; brands: BrandRosterGroup[] }
export interface ProcessBrandAssignments { brand: Brand | { brand_id: string; brand_name: string | null }; assignments: RosterAssignment[]; weekly_offs?: RosterAssignment[] }
export interface ProcessRosterGroup { process: Process | { process_id: string; process_name: string | null }; brands: ProcessBrandAssignments[] }
export interface ProcessRosterView { view: "process"; roster: Roster; processes: ProcessRosterGroup[] }
export type RosterView = CompanyRosterView | PodRosterView | BrandRosterView | ProcessRosterView | EmployeeRosterView;

import type { Weekday } from "./master-data";
export interface AvailabilityImpactChange { change_type: "availability"; employee_id: string; workable_days: Weekday[]; weekly_off_per_week?: number | null }
export interface TimeOffImpactChange { change_type: "time_off"; employee_id: string; time_off_type: "planned_leave" | "comp_off"; start_date: string; end_date: string; status: "pending" | "approved" | "rejected"; reason?: string | null; time_off_id?: string | null }
export interface EligibilityImpactChange { change_type: "eligibility"; employee_id: string; brand_id: string; process_id: string; is_active: boolean }
export interface OperatingRuleImpactChange { change_type: "operating_rule"; brand_id: string; process_id: string; operating_days: Weekday[]; public_holiday_policy: "operate" | "closed"; minimum_staffing: number; coverage_overrides?: Record<string, unknown>[]; is_active?: boolean }
export type ImpactChange = AvailabilityImpactChange | TimeOffImpactChange | EligibilityImpactChange | OperatingRuleImpactChange;
export interface ChangeImpactResult { valid: boolean; change_type: ImpactChange["change_type"]; roster_id: string; current_version: number; affected_dates: string[]; affected_employees: string[]; affected_brands: string[]; affected_processes: string[]; staffing_impact: Record<string, unknown>[]; conflicts: Record<string, unknown>[]; warnings: Record<string, unknown>[]; summary: Record<string, unknown> }
