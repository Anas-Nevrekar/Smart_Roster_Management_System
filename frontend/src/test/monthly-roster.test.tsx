import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MonthlyRosterPage } from "../features/monthly-roster/MonthlyRosterPage";
import { masterDataService, rosterService } from "../services/api";
import type { Employee, Brand, Process, Pod, PublicHoliday, TimeOff } from "../types/master-data";
import type { Roster, RosterAssignment, CoverageRow } from "../types/roster";
import type { CompanyRosterView, PodRosterView, BrandRosterView, ProcessRosterView, EmployeeRosterView, RosterView } from "../types/roster-views";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const roster: Roster = { id: "roster-2026-12", month: 12, year: 2026, status: "draft", generated_at: "2026-11-23T00:00:00Z", published_at: null, generated_by: null, published_by: null, created_at: "", updated_at: "", version: 7, assignment_count: 2, weekly_off_count: 1, summary: { total_assignments: 2, total_weekly_offs: 1, total_requirements: 1, requirements_satisfied: 1, coverage_gaps: 0, active_employees: 1, active_brands: 1, active_processes: 1 }, latest_validation: { valid: true, errors: [], summary: { total_assignments: 2, total_weekly_offs: 1, total_requirements: 1, requirements_satisfied: 1, coverage_gaps: 0, active_employees: 1, active_brands: 1, active_processes: 1 }, validated_at: "2026-11-23T00:00:00Z" } };
const employee: Employee = { id: "E001", employee_id: "E001", full_name: "Ari Example", email: "ari@example.com", pod_id: "PD1", is_active: true, weekly_off_per_week: 1, workable_days: ["Monday", "Tuesday"], created_at: "", updated_at: "" };
const pod: Pod = { id: "PD1", pod_id: "PD1", pod_name: "Team One", pod_lead_id: "E001", description: null, is_active: true, created_at: "", updated_at: "" };
const brand: Brand = { id: "B1", brand_id: "B1", brand_name: "Northstar", description: null, is_active: true, created_at: "", updated_at: "" };
const brand2: Brand = { id: "B2", brand_id: "B2", brand_name: "Cedar", description: null, is_active: true, created_at: "", updated_at: "" };
const process: Process = { id: "P1", process_id: "P1", process_name: "Support", description: null, is_active: true, created_at: "", updated_at: "" };
const process2: Process = { id: "P2", process_id: "P2", process_name: "Retention", description: null, is_active: true, created_at: "", updated_at: "" };
const a1: RosterAssignment = { id: "A1", roster_id: roster.id, employee_id: "E001", employee_name: "Ari Example", pod_id: "PD1", pod_name: "Team One", assignment_date: "2026-12-01", status: "working", brand_id: "B1", brand_name: "Northstar", process_id: "P1", process_name: "Support", created_at: "", updated_at: "" };
const a2: RosterAssignment = { ...a1, id: "A2", brand_id: "B2", brand_name: "Cedar", process_id: "P2", process_name: "Retention" };
const off: RosterAssignment = { ...a1, id: "WO1", assignment_date: "2026-12-02", status: "weekly_off", brand_id: null, brand_name: null, process_id: null, process_name: null };
const company: CompanyRosterView = { view: "company", roster, assignments: [a1, a2], weekly_offs: [off] };
const podView: PodRosterView = { view: "pod", roster, pods: [{ pod, pod_lead: employee, employees: [{ employee_id: "E001", employee_name: "Ari Example", pod_id: "PD1", pod_name: "Team One", assignments: [a1, a2], weekly_offs: [off] }] }] };
const brandView: BrandRosterView = { view: "brand", roster, brands: [{ brand, processes: [{ process, assignments: [a1], weekly_offs: [off] }] }, { brand: brand2, processes: [{ process: process2, assignments: [a2], weekly_offs: [off] }] }] };
const processView: ProcessRosterView = { view: "process", roster, processes: [{ process, brands: [{ brand, assignments: [a1], weekly_offs: [off] }] }, { process: process2, brands: [{ brand: brand2, assignments: [a2], weekly_offs: [off] }] }] };
const employeeView: EmployeeRosterView = { view: "employee", roster, employees: [{ employee_id: "E001", employee_name: "Ari Example", pod_id: "PD1", pod_name: "Team One", assignments: [a1, a2], weekly_offs: [off] }] };
const holiday: PublicHoliday = { id: "H1", holiday_name: "Founders Day", holiday_date: "2026-12-15", description: null, created_at: "", updated_at: "" };
const leave: TimeOff = { id: "L1", time_off_id: "L1", employee_id: "E001", time_off_type: "planned_leave", start_date: "2026-12-03", end_date: "2026-12-03", status: "approved", reason: null, approved_by: null, created_at: "", updated_at: "" };
const coverageRow: CoverageRow = { date: "2026-12-01", brand_id: "B1", brand_name: "Northstar", process_id: "P1", process_name: "Support", required_staffing: 2, actual_staffing: 1, staffing_gap: 1, status: "understaffed" };
function setup(options: { saved?: boolean; status?: "draft" | "published"; stale?: boolean | null } = {}) {
 const savedRoster = { ...roster, ...(options.status ? { status: options.status } : {}), ...(options.stale !== undefined ? { master_data_stale: options.stale } : {}) };
 const list = vi.spyOn(rosterService, "list").mockImplementation(async filters => filters?.month === 12 && options.saved !== false ? [savedRoster] : []);
 const get = vi.spyOn(rosterService, "get").mockResolvedValue(savedRoster);
 const view = vi.spyOn(rosterService, "view").mockImplementation(async (_id, name) => ({ company, pod: podView, brand: brandView, process: processView, employee: employeeView }[name] as RosterView));
 const coverageRequest = vi.spyOn(rosterService, "coverage").mockResolvedValue({ data: [coverageRow], summary: { total_requirements: 1, requirements_satisfied: 0, coverage_gaps: 1, total_working_assignments: 2, total_weekly_offs: 1 } });
 vi.spyOn(masterDataService, "employees").mockResolvedValue([employee]); vi.spyOn(masterDataService, "pods").mockResolvedValue([pod]); vi.spyOn(masterDataService, "brands").mockResolvedValue([brand, brand2]); vi.spyOn(masterDataService, "processes").mockResolvedValue([process, process2]); vi.spyOn(masterDataService, "timeOff").mockResolvedValue([leave]); vi.spyOn(masterDataService, "publicHolidays").mockResolvedValue([holiday]);
 render(<MonthlyRosterPage/>);
 return { list, get, view, coverage: coverageRequest, savedRoster };
}
async function chooseDecember() { await userEvent.selectOptions(screen.getByRole("combobox", { name: "Roster month" }), "12"); await waitFor(() => expect(rosterService.list).toHaveBeenLastCalledWith({ month: 12, year: new Date().getFullYear() })); }

describe("Task 9 monthly roster", () => {
 it("loads a saved roster and preserves multiple same-day assignments and weekly offs", async () => {
  setup(); await chooseDecember();
  expect(await screen.findByText("Ari Example")).toBeInTheDocument();
  expect(screen.getAllByText("Northstar").length).toBeGreaterThan(0);
  expect(within(screen.getAllByRole("table").at(-1)!).getByText("Cedar")).toBeInTheDocument();
  expect(screen.getByText(/Weekly Off/)).toBeInTheDocument();
  expect(screen.getByText("Holiday · Founders Day")).toBeInTheDocument();
 });
 it("switches to the pod, brand, process and employee view APIs", async () => {
  setup(); await chooseDecember();
  for (const [label, endpoint] of [["Pod-wise", "pod"], ["Brand-wise", "brand"], ["Process-wise", "process"], ["Employee-wise", "employee"]] as const) {
   await userEvent.click(screen.getByRole("tab", { name: label }));
   await waitFor(() => expect(rosterService.view).toHaveBeenLastCalledWith(roster.id, endpoint));
  }
 });
 it("requires a brand selection and shows only actual assignments for that brand and process", async () => {
  setup(); await chooseDecember(); await userEvent.click(screen.getByRole("tab", { name: "Brand-wise" }));
  expect(await screen.findByText("Select a brand to inspect its roster.")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Brand-wise brand selector" }), "B1");
  expect(await screen.findByRole("heading", { name: "Northstar" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Support" })).toBeInTheDocument();
  expect(screen.getByText("Ari Example")).toBeInTheDocument();
  expect(within(screen.getAllByRole("table").at(-1)!).queryByText("Cedar")).not.toBeInTheDocument();
  expect(screen.getByText("WO · Weekly Off")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Brand-wise process selector" }), "P1");
  expect(screen.getByRole("heading", { name: "Support" })).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Brand-wise brand selector" }), "B2");
  expect(await screen.findByRole("heading", { name: "Cedar" })).toBeInTheDocument();
  expect(within(screen.getAllByRole("table").at(-1)!).getByText("Cedar")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Brand-wise brand selector" }), "");
  expect(screen.getByText("Select a brand to inspect its roster.")).toBeInTheDocument();
 });
 it("shows process-wise brands and assignments only after selecting a configured process", async () => {
  setup(); await chooseDecember(); await userEvent.click(screen.getByRole("tab", { name: "Process-wise" }));
  expect(await screen.findByText("Select a process to inspect its roster.")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Process-wise process selector" }), "P1");
  expect(await screen.findByRole("heading", { name: "Support" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Northstar" })).toBeInTheDocument();
  expect(screen.getByText("Ari Example")).toBeInTheDocument();
  expect(within(screen.getAllByRole("table").at(-1)!).queryByText("Cedar")).not.toBeInTheDocument();
 });
 it("requires an employee selection and shows that employee's assignments across brands", async () => {
  setup(); await chooseDecember(); await userEvent.click(screen.getByRole("tab", { name: "Employee-wise" }));
  expect(await screen.findByText("Select an employee to inspect their roster.")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Employee-wise employee selector" }), "E001");
  expect(await screen.findByText("Northstar")).toBeInTheDocument();
  expect(within(screen.getAllByRole("table").at(-1)!).getByText("Cedar")).toBeInTheDocument();
 });
 it("applies combined pod, brand, process, search, status and date filters to saved assignment records", async () => {
  setup(); await chooseDecember();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Roster pod filter" }), "PD1");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Roster brand filter" }), "B1");
  expect(within(screen.getByRole("table")).getByText("Northstar")).toBeInTheDocument(); expect(within(screen.getByRole("table")).queryByText("Cedar")).not.toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Roster process filter" }), "P1");
  await userEvent.type(screen.getByRole("textbox", { name: "Search employee" }), "Ari");
  expect(screen.getByText("Ari Example")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Assignment status filter" }), "weekly_off");
  await userEvent.type(screen.getByLabelText("Roster date from"), "2026-12-02");
  await userEvent.type(screen.getByLabelText("Roster date to"), "2026-12-02");
  expect(screen.getByText("WO · Weekly Off")).toBeInTheDocument(); expect(within(screen.getByRole("table")).queryByText("Northstar")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(within(screen.getByRole("table")).getByText("Northstar")).toBeInTheDocument(); expect(within(screen.getByRole("table")).getByText("Cedar")).toBeInTheDocument();
 });
 it("confirms safe regeneration and keeps the previous roster visible when generation fails", async () => {
  setup(); await chooseDecember();
  const regenerate = vi.spyOn(rosterService, "regenerate").mockResolvedValue({ success: false, month: 12, year: 2026, roster, summary: { total_assignments: 0, total_weekly_offs: 0, total_requirements: 1, requirements_satisfied: 0, coverage_gaps: 1, active_employees: 1, active_brands: 1, active_processes: 1 }, assignments: [], weekly_offs: [], validation: { is_valid: false, errors: [], audit: {} as never }, diagnostics: [{ code: "STAFFING_GAP", message: "A required shift has no eligible employee." }] });
  await userEvent.click(await screen.findByRole("button", { name: "Regenerate Roster" }));
  expect(await screen.findByRole("dialog", { name: "Regenerate December 2026 roster?" })).toBeInTheDocument();
  expect(screen.getByText(/Current roster version: 7/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(regenerate).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Regenerate Roster" }));
  await userEvent.click(screen.getByRole("button", { name: "Confirm Regeneration" }));
  await waitFor(() => expect(regenerate).toHaveBeenCalledWith(roster.id, roster.version));
  expect((await screen.findAllByText("Regeneration failed. Your previous saved roster has been preserved.")).length).toBeGreaterThan(0);
  expect(screen.getByText("Ari Example")).toBeInTheDocument();
  expect(screen.getByText(/Validation: Valid/)).toBeInTheDocument();
  expect(screen.getByText("A required shift has no eligible employee.")).toBeInTheDocument();
 });
 it("refreshes the saved roster, selected view and coverage after successful regeneration", async () => {
  const { savedRoster, get, view, coverage } = setup(); await chooseDecember();
  const before = { rosterGets: get.mock.calls.length, views: view.mock.calls.length, coverage: coverage.mock.calls.length };
  const regenerate = vi.spyOn(rosterService, "regenerate").mockImplementation(async (_id, version) => {
   savedRoster.version = version + 1; savedRoster.assignment_count = 1; savedRoster.weekly_off_count = 1;
   return { success: true, month: 12, year: 2026, roster: savedRoster, summary: savedRoster.summary as never, assignments: [], weekly_offs: [], validation: { is_valid: true, errors: [], audit: {} as never }, diagnostics: [] };
  });
  await userEvent.click(await screen.findByRole("button", { name: "Regenerate Roster" }));
  await userEvent.click(screen.getByRole("button", { name: "Confirm Regeneration" }));
  await waitFor(() => expect(regenerate).toHaveBeenCalledWith(roster.id, roster.version));
  expect((await screen.findAllByText("Draft roster regenerated from the latest master data.")).length).toBeGreaterThan(0);
  await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(before.rosterGets));
  await waitFor(() => expect(view.mock.calls.length).toBeGreaterThan(before.views));
  await waitFor(() => expect(coverage.mock.calls.length).toBeGreaterThan(before.coverage));
  expect(screen.getByText("Version 8")).toBeInTheDocument();
 });
 it("shows a stale-version regeneration conflict and reloads the latest saved roster", async () => {
  const { savedRoster } = setup(); await chooseDecember();
  vi.spyOn(rosterService, "regenerate").mockImplementation(async () => { savedRoster.version = 8; throw { code: "STALE_ROSTER_VERSION", message: "The roster changed since it was read. Refresh and retry.", status: 409 }; });
  await userEvent.click(await screen.findByRole("button", { name: "Regenerate Roster" }));
  await userEvent.click(screen.getByRole("button", { name: "Confirm Regeneration" }));
  expect((await screen.findAllByText(/Regeneration failed\. Your previous saved roster has been preserved\./)).length).toBeGreaterThan(0);
  expect(await screen.findByText("Version 8")).toBeInTheDocument();
  expect(screen.getByText("Ari Example")).toBeInTheDocument();
 });
 it("filters coverage and opens the related brand view", async () => {
  setup(); await chooseDecember(); await userEvent.click(screen.getByRole("tab", { name: "Coverage" }));
  expect(await screen.findByText("understaffed")).toBeInTheDocument(); expect(screen.getByText("Requirements")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Coverage status" }), "satisfied");
  expect(await screen.findByText("No coverage rows match these filters.")).toBeInTheDocument();
 });
 it("submits a new assignment with the current version after eligibility selection", async () => {
  setup(); vi.spyOn(masterDataService, "eligibility").mockResolvedValue([{ id: "EL1", employee_id: "E001", brand_id: "B1", process_id: "P1", is_active: true, created_at: "", updated_at: "" }]);
  const add = vi.spyOn(rosterService, "addAssignment").mockResolvedValue({ success: true, roster_version: 8 });
  await chooseDecember(); await userEvent.click(await screen.findByRole("button", { name: "Add assignment" }));
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Employee" }), "E001");
  await userEvent.type(screen.getByLabelText(/Date/), "2026-12-04");
  await waitFor(() => expect(screen.getAllByRole("option", { name: "Northstar" }).length).toBeGreaterThan(0));
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Brand" }), "B1");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Process" }), "P1");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(add).toHaveBeenCalledWith(roster.id, 7, { employee_id: "E001", assignment_date: "2026-12-04", brand_id: "B1", process_id: "P1" }));
 });
 it("keeps the assignment visible when a confirmed deletion is rejected", async () => {
  setup(); const remove = vi.spyOn(rosterService, "deleteAssignment").mockRejectedValue({ code: "STAFFING_GAP", message: "Removing this assignment would create a staffing gap." });
  await chooseDecember(); await screen.findByText("Ari Example");
  await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);
  expect(remove).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Remove assignment" }));
  await waitFor(() => expect(remove).toHaveBeenCalledWith(roster.id, "A1", 7));
  expect(screen.getByText("Ari Example")).toBeInTheDocument();
 });
 it("submits a discriminated time-off impact preview without applying it", async () => {
  setup(); const preview = vi.spyOn(rosterService, "checkImpact").mockResolvedValue({ valid: false, change_type: "time_off", roster_id: roster.id, current_version: 7, affected_dates: ["2026-12-03"], affected_employees: ["E001"], affected_brands: ["B1"], affected_processes: ["P1"], staffing_impact: [], conflicts: [{ code: "STAFFING_GAP", date: "2026-12-03", message: "The proposed change creates a staffing gap." }], warnings: [], summary: { new_conflicts: 1 } });
  await chooseDecember(); await userEvent.click(screen.getByRole("button", { name: "Change impact" }));
  const dialog = screen.getByRole("dialog", { name: "Preview change impact" });
  expect(dialog).toHaveClass("max-h-[calc(100dvh-2rem)]", "overflow-hidden");
  expect(dialog.children[1]).toHaveClass("min-h-0", "overflow-y-auto");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Proposed change" }), "time_off");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Employee" }), "E001");
  await userEvent.type(screen.getByLabelText("Start date"), "2026-12-03"); await userEvent.type(screen.getByLabelText("End date"), "2026-12-03");
  await userEvent.click(screen.getByRole("button", { name: "Preview impact" }));
  await waitFor(() => expect(preview).toHaveBeenCalledWith(roster.id, { change: { change_type: "time_off", employee_id: "E001", time_off_type: "planned_leave", start_date: "2026-12-03", end_date: "2026-12-03", status: "approved" } }));
  expect(await screen.findByText(/This is a preview. No changes have been saved./)).toBeInTheDocument();
  expect(await screen.findByText(/The proposed change creates a staffing gap/)).toBeInTheDocument();
 });
 it("validates and publishes only after confirmation, then reflects published state", async () => {
  const { savedRoster } = setup(); const validate = vi.spyOn(rosterService, "validate").mockResolvedValue({ success: true, roster_id: roster.id, valid: true, errors: [], warnings: [], summary: roster.summary as never, diagnostics: [], validated_at: "2026-11-23T00:00:00Z", version: 7 });
  const publish = vi.spyOn(rosterService, "publish").mockImplementation(async () => { savedRoster.status = "published"; return savedRoster; });
  await chooseDecember(); await userEvent.click(await screen.findByRole("button", { name: "Validate Roster" })); await waitFor(() => expect(validate).toHaveBeenCalledWith(roster.id));
  expect(await screen.findByText("0 errors · 0 warnings · 0 coverage gaps")).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Publish Roster" })); expect(publish).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Confirm" })); await waitFor(() => expect(publish).toHaveBeenCalledWith(roster.id));
  expect(await screen.findByText("published")).toBeInTheDocument();
 });
 it("shows generation conflicts instead of presenting a saved roster", async () => {
  setup({ saved: false }); const generate = vi.spyOn(rosterService, "generate").mockResolvedValue({ success: false, month: 12, year: new Date().getFullYear(), summary: { total_assignments: 0, total_weekly_offs: 0, total_requirements: 0, requirements_satisfied: 0, coverage_gaps: 0, active_employees: 1, active_brands: 1, active_processes: 1 }, assignments: [], weekly_offs: [], validation: { is_valid: false, errors: [], audit: {} as never }, diagnostics: [{ code: "APPROVED_TIME_OFF_CONFLICT", message: "Approved leave conflict", date: "2026-12-08", employee_id: "E001", brand_id: "B1", process_id: "P1" }] });
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Roster month" }), "12"); await userEvent.click(await screen.findByRole("button", { name: "Generate Roster" })); await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
  await waitFor(() => expect(generate).toHaveBeenCalledWith(12, new Date().getFullYear())); expect(await screen.findByText("No roster for December " + new Date().getFullYear())).toBeInTheDocument(); expect(screen.getByText("APPROVED_TIME_OFF_CONFLICT")).toBeInTheDocument();
 });
 it("renders a read-only published roster with edit actions disabled", async () => {
  setup({ status: "published" }); await chooseDecember(); expect(await screen.findByText("published")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Add assignment" })).not.toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument(); expect(screen.getByRole("button", { name: "Publish Roster" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Regenerate Roster" })).toBeDisabled();
 });
 it("warns when generation inputs have changed since the saved roster was generated", async () => {
  setup({ stale: true }); await chooseDecember();
  expect(await screen.findByText("Master data has changed since this roster was generated. Regeneration is recommended.")).toBeInTheDocument();
 });
});
