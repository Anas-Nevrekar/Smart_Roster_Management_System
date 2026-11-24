import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosHeaders } from "axios";
import { EmployeesPage } from "../features/management/EmployeesPage";
import { BrandsProcessesPage } from "../features/management/BrandsProcessesPage";
import { PodsPage } from "../features/management/PodsPage";
import { LeaveAvailabilityPage } from "../features/management/LeaveAvailabilityPage";
import { OperatingRulesPage } from "../features/management/OperatingRulesPage";
import { PublicHolidaysPage } from "../features/management/PublicHolidaysPage";
import { masterDataService } from "../services/api";
import type { Brand, Employee, OperatingRule, Pod, Process, PublicHoliday, TimeOff } from "../types/master-data";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const employee: Employee = { id: "E001", employee_id: "E001", full_name: "Ari Example", email: "ari@example.com", pod_id: null, is_active: true, weekly_off_per_week: 1, workable_days: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], created_at: "", updated_at: "" };
const brand: Brand = { id: "B1", brand_id: "B1", brand_name: "Northstar", description: null, is_active: true, created_at: "", updated_at: "" };
const process: Process = { id: "P1", process_id: "P1", process_name: "Support", description: null, is_active: true, created_at: "", updated_at: "" };
const pod: Pod = { id: "PD1", pod_id: "PD1", pod_name: "Team One", pod_lead_id: null, description: null, is_active: true, created_at: "", updated_at: "" };
const leave: TimeOff = { id: "L1", time_off_id: "L1", employee_id: "E001", time_off_type: "planned_leave", start_date: "2026-12-01", end_date: "2026-12-02", status: "pending", reason: "Personal", approved_by: null, created_at: "", updated_at: "" };
const rule: OperatingRule = { id: "R1", brand_id: "B1", brand_name: "Northstar", process_id: "P1", process_name: "Support", operating_days: ["Monday"], public_holiday_policy: "closed", minimum_staffing: 1, coverage_overrides: [], is_active: true, created_at: "", updated_at: "" };
const holiday: PublicHoliday = { id: "H1", holiday_name: "Founders Day", holiday_date: "2026-12-15", description: null, created_at: "", updated_at: "" };

describe("Task 8 master data screens", () => {
 it("searches employees through the list filter and submits a validated employee create payload", async () => {
  const employees = vi.spyOn(masterDataService, "employees").mockResolvedValue([employee]); vi.spyOn(masterDataService, "pods").mockResolvedValue([]); vi.spyOn(masterDataService, "brands").mockResolvedValue([]); vi.spyOn(masterDataService, "processes").mockResolvedValue([]); vi.spyOn(masterDataService, "allEligibility").mockResolvedValue([]); const create = vi.spyOn(masterDataService, "createEmployee").mockResolvedValue(employee);
  render(<EmployeesPage/>); expect(await screen.findByText("ari@example.com")).toBeInTheDocument(); await userEvent.type(screen.getByRole("textbox", { name: "Search" }), "Ari"); await waitFor(() => expect(employees).toHaveBeenLastCalledWith({ search: "Ari", pod_id: undefined, is_active: undefined }));
  await userEvent.click(screen.getByRole("button", { name: "Add employee" })); await userEvent.type(screen.getByLabelText(/Employee ID/), "E002"); await userEvent.type(screen.getByLabelText(/Full name/), "Ari New"); await userEvent.type(screen.getByLabelText(/Email/), "new@example.com"); await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ employee_id: "E002", full_name: "Ari New", email: "new@example.com", is_active: true, weekly_off_per_week: 1 })));
 });
 it("loads and replaces an employee eligibility set without duplicate pairs", async () => {
  vi.spyOn(masterDataService, "employees").mockResolvedValue([employee]); vi.spyOn(masterDataService, "pods").mockResolvedValue([]); vi.spyOn(masterDataService, "brands").mockResolvedValue([brand]); vi.spyOn(masterDataService, "processes").mockResolvedValue([process]); vi.spyOn(masterDataService, "allEligibility").mockResolvedValue([]); vi.spyOn(masterDataService, "eligibility").mockResolvedValue([]); const save = vi.spyOn(masterDataService, "replaceEligibility").mockResolvedValue([]);
  render(<EmployeesPage/>); await userEvent.click(await screen.findByRole("button", { name: "Eligibility" })); const checkbox = await screen.findByRole("checkbox", { name: "Northstar / Support" }); await userEvent.click(checkbox); await userEvent.click(screen.getByRole("button", { name: "Save" })); await waitFor(() => expect(save).toHaveBeenCalledWith("E001", [{ brand_id: "B1", process_id: "P1", is_active: true }]));
 });
 it("edits supported employee fields and confirms status changes", async () => {
  vi.spyOn(masterDataService, "employees").mockResolvedValue([employee]); vi.spyOn(masterDataService, "pods").mockResolvedValue([]); vi.spyOn(masterDataService, "brands").mockResolvedValue([]); vi.spyOn(masterDataService, "processes").mockResolvedValue([]); vi.spyOn(masterDataService, "allEligibility").mockResolvedValue([]);
  const update = vi.spyOn(masterDataService, "updateEmployee").mockResolvedValue({ ...employee, full_name: "Ari Updated" }); const status = vi.spyOn(masterDataService, "setEmployeeStatus").mockResolvedValue({ ...employee, is_active: false });
  render(<EmployeesPage/>); await userEvent.click(await screen.findByRole("button", { name: "Edit" })); expect(screen.getByLabelText(/Employee ID/)).toBeDisabled(); await userEvent.clear(screen.getByLabelText(/Full name/)); await userEvent.type(screen.getByLabelText(/Full name/), "Ari Updated"); await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(update).toHaveBeenCalledWith("E001", expect.objectContaining({ employee_id: "E001", full_name: "Ari Updated" })));
  await userEvent.click(await screen.findByRole("button", { name: "Deactivate" })); expect(status).not.toHaveBeenCalled(); await userEvent.click(screen.getByRole("button", { name: "Confirm" })); await waitFor(() => expect(status).toHaveBeenCalledWith("E001", false));
 });
 it("saves availability separately and keeps leave state visible", async () => {
  vi.spyOn(masterDataService, "employees").mockResolvedValue([employee]); vi.spyOn(masterDataService, "timeOff").mockResolvedValue([]); vi.spyOn(masterDataService, "availability").mockResolvedValue({ workable_days: ["Monday"], weekly_off_per_week: 1, time_off: [leave] }); const save = vi.spyOn(masterDataService, "updateAvailability").mockResolvedValue(employee);
  render(<LeaveAvailabilityPage/>); await userEvent.click(screen.getByRole("tab", { name: "Employee Availability" })); await userEvent.selectOptions(screen.getByRole("combobox", { name: /Employee/ }), "E001"); expect(await screen.findByText(/pending/)).toBeInTheDocument(); await userEvent.click(screen.getByRole("button", { name: "Save" })); await waitFor(() => expect(save).toHaveBeenCalledWith("E001", { workable_days: ["Monday"], weekly_off_per_week: 1 }));
 });
 it("creates leave as pending and requires confirmation before approval", async () => {
  vi.spyOn(masterDataService, "employees").mockResolvedValue([employee]); vi.spyOn(masterDataService, "timeOff").mockResolvedValue([leave]); const create = vi.spyOn(masterDataService, "createTimeOff").mockResolvedValue(leave); const approve = vi.spyOn(masterDataService, "approveTimeOff").mockResolvedValue({ ...leave, status: "approved" });
  render(<LeaveAvailabilityPage/>); expect(await screen.findByText("Personal")).toBeInTheDocument(); await userEvent.click(screen.getByRole("button", { name: "New request" })); await userEvent.selectOptions(screen.getByRole("combobox", { name: /Employee/ }), "E001"); await userEvent.type(screen.getByLabelText(/Start date/), "2026-12-20"); await userEvent.type(screen.getByLabelText(/End date/), "2026-12-21"); await userEvent.click(screen.getByRole("button", { name: "Save" })); await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ employee_id: "E001", status: "pending" })));
  await userEvent.click(await screen.findByRole("button", { name: "Approve" })); await userEvent.click(screen.getByRole("button", { name: "Confirm" })); await waitFor(() => expect(approve).toHaveBeenCalledWith("L1"));
 });
 it("switches brand/process tabs and saves a process", async () => {
  vi.spyOn(masterDataService, "brands").mockResolvedValue([brand]); vi.spyOn(masterDataService, "processes").mockResolvedValue([process]); vi.spyOn(masterDataService, "allEligibility").mockResolvedValue([]); const create = vi.spyOn(masterDataService, "createProcess").mockResolvedValue(process);
  render(<BrandsProcessesPage/>); expect(await screen.findByText("Northstar")).toBeInTheDocument(); await userEvent.click(screen.getByRole("tab", { name: "processes" })); expect(await screen.findByText("Support")).toBeInTheDocument(); await userEvent.click(screen.getByRole("button", { name: "Add process" })); await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Retention"); await userEvent.click(screen.getByRole("button", { name: "Save" })); await waitFor(() => expect(create).toHaveBeenCalledWith({ process_name: "Retention", description: null, is_active: true }));
 });
 it("creates a brand and confirms deactivation", async () => {
  vi.spyOn(masterDataService, "brands").mockResolvedValue([brand]); vi.spyOn(masterDataService, "processes").mockResolvedValue([process]); vi.spyOn(masterDataService, "allEligibility").mockResolvedValue([]);
  const create = vi.spyOn(masterDataService, "createBrand").mockResolvedValue(brand); const status = vi.spyOn(masterDataService, "setBrandStatus").mockResolvedValue({ ...brand, is_active: false });
  render(<BrandsProcessesPage/>); await screen.findByText("Northstar"); await userEvent.click(screen.getByRole("button", { name: "Add brand" })); await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "New Brand"); await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith({ brand_name: "New Brand", description: null, is_active: true })); await userEvent.click(await screen.findByRole("button", { name: "Deactivate" })); await userEvent.click(screen.getByRole("button", { name: "Confirm" })); await waitFor(() => expect(status).toHaveBeenCalledWith("B1", false));
 });
 it("updates pod membership only after confirmation", async () => {
  vi.spyOn(masterDataService, "pods").mockResolvedValue([pod]); vi.spyOn(masterDataService, "employees").mockResolvedValue([employee]); vi.spyOn(masterDataService, "podEmployees").mockResolvedValue([]); const save = vi.spyOn(masterDataService, "replacePodMembers").mockResolvedValue([employee]);
  render(<PodsPage/>); await userEvent.click(await screen.findByRole("button", { name: "Members" })); await userEvent.click(await screen.findByRole("checkbox", { name: /Ari Example/ })); await userEvent.click(screen.getByRole("button", { name: "Save membership" })); expect(save).not.toHaveBeenCalled(); await userEvent.click(screen.getByRole("button", { name: "Confirm" })); await waitFor(() => expect(save).toHaveBeenCalledWith("PD1", ["E001"]));
 });
 it("creates pods with an active lead and updates the lead through its dedicated endpoint", async () => {
  vi.spyOn(masterDataService, "pods").mockResolvedValue([pod]); vi.spyOn(masterDataService, "employees").mockResolvedValue([employee]); const create = vi.spyOn(masterDataService, "createPod").mockResolvedValue(pod); const lead = vi.spyOn(masterDataService, "setPodLead").mockResolvedValue({ ...pod, pod_lead_id: "E001" });
  render(<PodsPage/>); await userEvent.click(await screen.findByRole("button", { name: "Add pod" })); await userEvent.type(screen.getByLabelText(/Pod name/), "Team Two"); await userEvent.selectOptions(screen.getByLabelText("Pod lead"), "E001"); await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith({ pod_name: "Team Two", pod_lead_id: "E001", description: null, is_active: true }));
  await userEvent.click(await screen.findByRole("button", { name: "Change lead" })); await userEvent.selectOptions(screen.getByRole("combobox", { name: "Active employee" }), "E001"); await userEvent.click(screen.getByRole("button", { name: "Save lead" })); await waitFor(() => expect(lead).toHaveBeenCalledWith("PD1", "E001"));
 });
 it("shows unsupported override guidance and rejects duplicate operating rules before submit", async () => {
  vi.spyOn(masterDataService, "operatingRules").mockResolvedValue([rule]); vi.spyOn(masterDataService, "brands").mockResolvedValue([brand]); vi.spyOn(masterDataService, "processes").mockResolvedValue([process]); const create = vi.spyOn(masterDataService, "createRule").mockResolvedValue(rule);
  render(<OperatingRulesPage/>); await userEvent.click(await screen.findByRole("button", { name: "Add rule" })); expect(screen.getByText(/overrides are unsupported/i)).toBeInTheDocument(); await userEvent.selectOptions(screen.getByLabelText(/Brand/), "B1"); await userEvent.selectOptions(screen.getByLabelText(/Process/), "P1"); await userEvent.click(screen.getByLabelText("Monday")); await userEvent.type(screen.getByLabelText(/Minimum staffing/), "2"); await userEvent.click(screen.getByRole("button", { name: "Save" })); expect(await screen.findByRole("alert")).toHaveTextContent("already exists"); expect(create).not.toHaveBeenCalled();
 });
 it("creates a holiday and renders backend duplicate-date errors", async () => {
  vi.spyOn(masterDataService, "publicHolidays").mockResolvedValue([holiday]); const create = vi.spyOn(masterDataService, "createHoliday").mockRejectedValue({ code: "DUPLICATE_HOLIDAY_DATE", message: "A holiday already exists for this date." });
  render(<PublicHolidaysPage/>); expect(await screen.findByText("Founders Day")).toBeInTheDocument(); await userEvent.click(screen.getByRole("button", { name: "Add holiday" })); await userEvent.type(screen.getByLabelText(/Holiday name/), "Another Day"); fireEvent.change(screen.getByLabelText(/Date/), { target: { value: "2026-12-15" } }); await userEvent.click(screen.getByRole("button", { name: "Save" })); await waitFor(() => expect(create).toHaveBeenCalled()); expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
 });
 it("confirms holiday deletion before calling the API", async () => {
  vi.spyOn(masterDataService, "publicHolidays").mockResolvedValue([holiday]); const remove = vi.spyOn(masterDataService, "deleteHoliday").mockResolvedValue({ data: {}, status: 204, statusText: "No Content", headers: {}, config: { headers: new AxiosHeaders() } });
  render(<PublicHolidaysPage/>); await userEvent.click(await screen.findByRole("button", { name: "Delete" })); expect(remove).not.toHaveBeenCalled(); await userEvent.click(screen.getByRole("button", { name: "Confirm" })); await waitFor(() => expect(remove).toHaveBeenCalledWith("H1"));
 });
});
