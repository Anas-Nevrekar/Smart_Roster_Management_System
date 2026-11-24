import { api } from "../lib/api";
import type { ApiHealth, ApiReadiness } from "../types/api";
import type { Brand, Employee, Eligibility, OperatingRule, Pod, Process, PublicHoliday, TimeOff, Weekday } from "../types/master-data";
import type { CoverageRow, CoverageSummary, GenerateRosterResult, Roster, RosterAssignment, ValidationResult } from "../types/roster";
import type { ImpactChange } from "../types/roster-views";
type Envelope<T> = { success: true; data: T; total?: number };
async function list<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T[]> { const { data } = await api.get<Envelope<T[]>>(path, { params }); return data.data; }
async function unwrap<T>(promise: Promise<{ data: Envelope<T> }>): Promise<T> { return (await promise).data.data; }
export interface EmployeeInput { employee_id: string; full_name: string; email: string; pod_id: string | null; is_active: boolean; weekly_off_per_week: number; workable_days: Weekday[] }
export interface PodInput { pod_name: string; pod_lead_id: string | null; description: string | null; is_active: boolean }
export interface NamedInput { description: string | null; is_active: boolean }
export interface RuleInput { brand_id: string; process_id: string; operating_days: Weekday[]; public_holiday_policy: "operate" | "closed"; minimum_staffing: number; coverage_overrides: { date: string; minimum_staffing: number }[]; is_active: boolean }
export interface TimeOffInput { employee_id: string; time_off_type: "planned_leave" | "comp_off"; start_date: string; end_date: string; status: "pending" | "approved" | "rejected"; reason: string | null; approved_by?: string | null }
export interface HolidayInput { holiday_name: string; holiday_date: string; description: string | null }
export interface ChangeImpactRequest { change: ImpactChange }
export const healthService = {
  health: async () => (await api.get<Envelope<ApiHealth>>("/health")).data.data,
  readiness: async () => (await api.get<Envelope<ApiReadiness>>("/ready")).data.data,
};
export const masterDataService = {
  employees: (filters?: { search?: string; pod_id?: string; is_active?: boolean }) => list<Employee>("/employees", filters), pods: () => list<Pod>("/pods"), brands: () => list<Brand>("/brands"),
  processes: () => list<Process>("/processes"), operatingRules: () => list<OperatingRule>("/operating-rules"),
  timeOff: (filters?: { employee_id?: string; status?: string; time_off_type?: string; start_date?: string; end_date?: string }) => list<TimeOff>("/time-off", filters), publicHolidays: (year?: number) => list<PublicHoliday>("/public-holidays", { year }),
  createEmployee: (body: EmployeeInput) => unwrap<Employee>(api.post("/employees", body)), updateEmployee: (id: string, body: EmployeeInput) => unwrap<Employee>(api.put(`/employees/${id}`, body)), setEmployeeStatus: (id: string, is_active: boolean) => unwrap<Employee>(api.patch(`/employees/${id}/status`, { is_active })),
  eligibility: (id: string) => list<Eligibility>(`/employees/${id}/eligibility`), replaceEligibility: async (id: string, items: Pick<Eligibility, "brand_id" | "process_id" | "is_active">[]) => (await api.put<Envelope<Eligibility[]>>(`/employees/${id}/eligibility`, { items })).data.data,
  allEligibility: () => list<Eligibility>("/eligibility"),
  availability: (id: string) => unwrap<{ workable_days: Weekday[]; weekly_off_per_week: number; time_off: TimeOff[] }>(api.get(`/employees/${id}/availability`)), updateAvailability: (id: string, body: { workable_days: Weekday[]; weekly_off_per_week: number }) => unwrap<Employee>(api.put(`/employees/${id}/availability`, body)),
  createBrand: (body: { brand_name: string } & NamedInput) => unwrap<Brand>(api.post("/brands", body)), updateBrand: (id: string, body: { brand_name: string } & NamedInput) => unwrap<Brand>(api.put(`/brands/${id}`, body)), setBrandStatus: (id: string, is_active: boolean) => unwrap<Brand>(api.patch(`/brands/${id}/status`, { is_active })),
  brandEmployees: (id: string) => list<Employee>(`/brands/${id}/employees`), brandProcesses: (id: string) => list<Process>(`/brands/${id}/processes`),
  createProcess: (body: { process_name: string } & NamedInput) => unwrap<Process>(api.post("/processes", body)), updateProcess: (id: string, body: { process_name: string } & NamedInput) => unwrap<Process>(api.put(`/processes/${id}`, body)), setProcessStatus: (id: string, is_active: boolean) => unwrap<Process>(api.patch(`/processes/${id}/status`, { is_active })),
  createPod: (body: PodInput) => unwrap<Pod>(api.post("/pods", body)), updatePod: (id: string, body: PodInput) => unwrap<Pod>(api.put(`/pods/${id}`, body)), deletePod: (id: string) => api.delete(`/pods/${id}`), podEmployees: (id: string) => list<Employee>(`/pods/${id}/employees`), replacePodMembers: async (id: string, employee_ids: string[]) => (await api.put<Envelope<Employee[]>>(`/pods/${id}/employees`, { employee_ids })).data.data, setPodLead: (id: string, pod_lead_id: string | null) => unwrap<Pod>(api.patch(`/pods/${id}/lead`, { pod_lead_id })),
  createTimeOff: (body: TimeOffInput) => unwrap<TimeOff>(api.post("/time-off", body)), updateTimeOff: (id: string, body: TimeOffInput) => unwrap<TimeOff>(api.put(`/time-off/${id}`, body)), approveTimeOff: (id: string) => unwrap<TimeOff>(api.patch(`/time-off/${id}/approve`)), rejectTimeOff: (id: string) => unwrap<TimeOff>(api.patch(`/time-off/${id}/reject`)), deleteTimeOff: (id: string) => api.delete(`/time-off/${id}`),
  createRule: (body: RuleInput) => unwrap<OperatingRule>(api.post("/operating-rules", body)), updateRule: (id: string, body: RuleInput) => unwrap<OperatingRule>(api.put(`/operating-rules/${id}`, body)), deleteRule: (id: string) => api.delete(`/operating-rules/${id}`),
  createHoliday: (body: HolidayInput) => unwrap<PublicHoliday>(api.post("/public-holidays", body)), updateHoliday: (id: string, body: HolidayInput) => unwrap<PublicHoliday>(api.put(`/public-holidays/${id}`, body)), deleteHoliday: (id: string) => api.delete(`/public-holidays/${id}`),
};
export const rosterService = {
  list: (filters?: { month?: number; year?: number; status?: string }) => list<Roster>("/rosters", filters),
  generate: async (month: number, year: number) => (await api.post<GenerateRosterResult>("/rosters/generate", { month, year })).data,
  regenerate: async (id: string, version: number) => (await api.post<GenerateRosterResult>(`/rosters/${id}/regenerate`, {}, { headers: { "If-Match": String(version) } })).data,
  get: async (id: string) => unwrap<Roster>(api.get(`/rosters/${id}`)),
  assignments: (id: string, filters?: Record<string, string>) => list<RosterAssignment>(`/rosters/${id}/assignments`, filters),
  weeklyOffs: (id: string, filters?: Record<string, string>) => list<RosterAssignment>(`/rosters/${id}/weekly-offs`, filters),
  view: async <T>(id: string, name: "company" | "pod" | "brand" | "process" | "employee") => unwrap<T>(api.get(`/rosters/${id}/views/${name}`)),
  coverage: async (id: string) => { const { data } = await api.get<{ data: CoverageRow[]; summary: CoverageSummary }>(`/rosters/${id}/coverage`); return data; },
  validate: async (id: string) => { const { data } = await api.post<ValidationResult>(`/rosters/${id}/validate`); return data; },
  publish: async (id: string) => unwrap<Roster>(api.post(`/rosters/${id}/publish`, {})),
  addAssignment: async (id: string, version: number, body: { employee_id: string; assignment_date: string; brand_id: string; process_id: string }) => (await api.post(`/rosters/${id}/assignments`, body, { headers: { "If-Match": String(version) } })).data,
  updateAssignment: async (id: string, assignmentId: string, version: number, body: { employee_id?: string; assignment_date?: string; brand_id?: string; process_id?: string }) => (await api.patch(`/rosters/${id}/assignments/${assignmentId}`, body, { headers: { "If-Match": String(version) } })).data,
  deleteAssignment: async (id: string, assignmentId: string, version: number) => (await api.delete(`/rosters/${id}/assignments/${assignmentId}`, { headers: { "If-Match": String(version) } })).data,
  checkImpact: async <T>(id: string, body: ChangeImpactRequest) => (await api.post<T>(`/rosters/${id}/check-impact`, body)).data,
};
