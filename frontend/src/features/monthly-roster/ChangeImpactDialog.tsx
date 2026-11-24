import { useState } from "react";
import { Dialog } from "../../components/ui/Dialog";
import { Select } from "../../components/ui/Select";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Badge, EmptyState } from "../../components/ui/Feedback";
import { Table } from "../../components/ui/Table";
import { getApiFailure } from "../../lib/api";
import { rosterService } from "../../services/api";
import type { Brand, Employee, Process, Weekday } from "../../types/master-data";
import type { Roster } from "../../types/roster";
import type { ChangeImpactResult, ImpactChange } from "../../types/roster-views";
import { Field } from "../management/shared";
const week: Weekday[] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
function createChange(kind: ImpactChange["change_type"]): ImpactChange {
 if (kind === "time_off") return { change_type: kind, employee_id: "", time_off_type: "planned_leave", start_date: "", end_date: "", status: "approved" };
 if (kind === "eligibility") return { change_type: kind, employee_id: "", brand_id: "", process_id: "", is_active: false };
 if (kind === "operating_rule") return { change_type: kind, brand_id: "", process_id: "", operating_days: [], public_holiday_policy: "closed", minimum_staffing: 0, coverage_overrides: [], is_active: true };
 return { change_type: kind, employee_id: "", workable_days: week, weekly_off_per_week: 1 };
}
function fieldValue(row: Record<string, unknown>, field: string): string { const value = row[field]; return typeof value === "string" || typeof value === "number" ? String(value) : "—"; }
export function ChangeImpactDialog({ open, roster, employees, brands, processes, onClose }: { open: boolean; roster: Roster; employees: Employee[]; brands: Brand[]; processes: Process[]; onClose: () => void }) {
 const [change, setChange] = useState<ImpactChange>(createChange("availability"));
 const [result, setResult] = useState<ChangeImpactResult | null>(null);
 const [error, setError] = useState("");
 const [busy, setBusy] = useState(false);
 function changeKind(kind: ImpactChange["change_type"]) { setChange(createChange(kind)); setResult(null); setError(""); }
 async function submit(event: React.FormEvent) {
  event.preventDefault(); setBusy(true); setError(""); setResult(null);
  try { setResult(await rosterService.checkImpact<ChangeImpactResult>(roster.id, { change })); }
  catch (e) { setError(getApiFailure(e).message); }
  finally { setBusy(false); }
 }
 return <Dialog open={open} title="Preview change impact" onClose={onClose}>
  <div className="mb-3 rounded border border-amber-200 bg-amber-50 p-3 text-sm font-medium text-amber-900">This is a preview. No changes have been saved.</div>
  <form onSubmit={submit} className="space-y-3">
   <Field label="Proposed change"><Select value={change.change_type} onChange={e => changeKind(e.target.value as ImpactChange["change_type"])}><option value="availability">Employee availability</option><option value="time_off">Employee time off</option><option value="eligibility">Employee eligibility</option><option value="operating_rule">Operating rule</option></Select></Field>
   {(change.change_type === "availability" || change.change_type === "time_off" || change.change_type === "eligibility") && <Field label="Employee"><Select required value={change.employee_id} onChange={e => setChange({ ...change, employee_id: e.target.value })}><option value="">Select employee</option>{employees.map(item => <option key={item.id} value={item.id}>{item.full_name} · {item.employee_id}</option>)}</Select></Field>}
   {change.change_type === "availability" && <>
    <Field label="Proposed workable weekdays"><div className="grid grid-cols-2 gap-2">{week.map(day => <label key={day} className="flex gap-2 text-sm"><input type="checkbox" checked={change.workable_days.includes(day)} onChange={e => setChange({ ...change, workable_days: e.target.checked ? [...change.workable_days, day] : change.workable_days.filter(item => item !== day) })}/>{day}</label>)}</div></Field>
    <Field label="Weekly offs per week"><Input type="number" min="0" max="7" value={change.weekly_off_per_week ?? 1} onChange={e => setChange({ ...change, weekly_off_per_week: Number(e.target.value) })}/></Field>
   </>}
   {change.change_type === "time_off" && <>
    <Field label="Leave type"><Select value={change.time_off_type} onChange={e => setChange({ ...change, time_off_type: e.target.value as "planned_leave" | "comp_off" })}><option value="planned_leave">Planned leave</option><option value="comp_off">Comp off</option></Select></Field>
    <Field label="Start date"><Input required type="date" value={change.start_date} onChange={e => setChange({ ...change, start_date: e.target.value })}/></Field>
    <Field label="End date"><Input required type="date" min={change.start_date} value={change.end_date} onChange={e => setChange({ ...change, end_date: e.target.value })}/></Field>
    <Field label="Proposed status"><Select value={change.status} onChange={e => setChange({ ...change, status: e.target.value as "pending" | "approved" | "rejected" })}><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option></Select></Field>
   </>}
   {(change.change_type === "eligibility" || change.change_type === "operating_rule") && <>
    <Field label="Brand"><Select required value={change.brand_id} onChange={e => setChange({ ...change, brand_id: e.target.value })}><option value="">Select brand</option>{brands.map(item => <option key={item.id} value={item.id}>{item.brand_name}</option>)}</Select></Field>
    <Field label="Process"><Select required value={change.process_id} onChange={e => setChange({ ...change, process_id: e.target.value })}><option value="">Select process</option>{processes.map(item => <option key={item.id} value={item.id}>{item.process_name}</option>)}</Select></Field>
   </>}
   {change.change_type === "eligibility" && <label className="flex gap-2 text-sm"><input type="checkbox" checked={change.is_active} onChange={e => setChange({ ...change, is_active: e.target.checked })}/>Proposed eligibility active</label>}
   {change.change_type === "operating_rule" && <>
    <Field label="Operating weekdays"><div className="grid grid-cols-2 gap-2">{week.map(day => <label key={day} className="flex gap-2 text-sm"><input type="checkbox" checked={change.operating_days.includes(day)} onChange={e => setChange({ ...change, operating_days: e.target.checked ? [...change.operating_days, day] : change.operating_days.filter(item => item !== day) })}/>{day}</label>)}</div></Field>
    <Field label="Public holiday policy"><Select value={change.public_holiday_policy} onChange={e => setChange({ ...change, public_holiday_policy: e.target.value as "operate" | "closed" })}><option value="closed">Closed</option><option value="operate">Operate</option></Select></Field>
    <Field label="Minimum staffing"><Input type="number" min="0" step="1" value={change.minimum_staffing} onChange={e => setChange({ ...change, minimum_staffing: Number(e.target.value) })}/></Field>
   </>}
   {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
   <div className="flex justify-end gap-2"><button type="button" className="rounded border px-3 py-2 text-sm" onClick={onClose}>Close</button><Button disabled={busy}>{busy ? "Checking…" : "Preview impact"}</Button></div>
  </form>
  {result && <section className="mt-4 space-y-3 border-t pt-3"><div className="flex items-center gap-2"><Badge tone={result.valid ? "green" : "red"}>{result.valid ? "No new blocking conflicts" : "Conflicts found"}</Badge><span className="text-xs text-slate-500">{result.affected_dates.length} affected dates</span></div><p className="text-xs text-slate-600">Employees: {result.affected_employees.join(", ") || "None"} · Brands: {result.affected_brands.join(", ") || "None"} · Processes: {result.affected_processes.join(", ") || "None"}</p>
   {result.staffing_impact.length > 0 && <Table headers={["Date", "Brand", "Process", "Before gap", "After gap"]}>{result.staffing_impact.map((item, index) => { const before = item.before && typeof item.before === "object" ? item.before as Record<string, unknown> : {}; const after = item.after && typeof item.after === "object" ? item.after as Record<string, unknown> : {}; return <tr key={index}><td className="px-3 py-2">{fieldValue(item, "date")}</td><td className="px-3 py-2">{fieldValue(item, "brand_name")}</td><td className="px-3 py-2">{fieldValue(item, "process_name")}</td><td className="px-3 py-2">{fieldValue(before, "staffing_gap")}</td><td className="px-3 py-2">{fieldValue(after, "staffing_gap")}</td></tr>; })}</Table>}
   {result.conflicts.length > 0 ? <div><h3 className="mb-1 font-medium text-rose-800">Conflicts</h3><ul className="list-inside list-disc text-sm text-rose-900">{result.conflicts.map((item, index) => <li key={index}>{fieldValue(item, "date")} · {fieldValue(item, "message") || fieldValue(item, "code")}</li>)}</ul></div> : <EmptyState title="No new conflicts found."/>}
   {result.warnings.length > 0 && <div><h3 className="mb-1 font-medium text-amber-800">Existing warnings</h3><ul className="list-inside list-disc text-sm text-amber-900">{result.warnings.map((item, index) => <li key={index}>{fieldValue(item, "message") || fieldValue(item, "code")}</li>)}</ul></div>}
  </section>}
 </Dialog>;
}
