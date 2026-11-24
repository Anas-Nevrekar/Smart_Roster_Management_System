import { useEffect, useState } from "react";
import { Dialog } from "../../components/ui/Dialog";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Button } from "../../components/ui/Button";
import { masterDataService, rosterService } from "../../services/api";
import { getApiFailure } from "../../lib/api";
import type { Employee, Brand, Process, Eligibility } from "../../types/master-data";
import type { Roster, RosterAssignment } from "../../types/roster";
import { Field, SaveBar } from "../management/shared";

export function AssignmentEditor({ open, roster, assignment, employees, brands, processes, onClose, onSaved }: {
 open: boolean; roster: Roster; assignment: RosterAssignment | null; employees: Employee[]; brands: Brand[]; processes: Process[];
 onClose: () => void; onSaved: () => void;
}) {
 const [employeeId, setEmployeeId] = useState(assignment?.employee_id ?? "");
 const [date, setDate] = useState(assignment?.assignment_date ?? "");
 const [brandId, setBrandId] = useState(assignment?.brand_id ?? "");
 const [processId, setProcessId] = useState(assignment?.process_id ?? "");
 const [eligibility, setEligibility] = useState<Eligibility[]>([]);
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState("");
 useEffect(() => {
  setEmployeeId(assignment?.employee_id ?? "");
  setDate(assignment?.assignment_date ?? "");
  setBrandId(assignment?.brand_id ?? "");
  setProcessId(assignment?.process_id ?? "");
  setError("");
  if (assignment) void loadEligibility(assignment.employee_id);
  else setEligibility([]);
 }, [assignment, open]);
 async function loadEligibility(id: string) {
  if (!id) { setEligibility([]); return; }
  try { setEligibility((await masterDataService.eligibility(id)).filter(item => item.is_active)); }
  catch (e) { setError(getApiFailure(e).message); }
 }
 async function chooseEmployee(id: string) {
  setEmployeeId(id);
  setBrandId("");
  setProcessId("");
  await loadEligibility(id);
 }
 async function save(event: React.FormEvent) {
  event.preventDefault();
  setError("");
  if (!employeeId || !date || !brandId || !processId) { setError("Choose an employee, date, brand and process."); return; }
  if (!date.startsWith(String(roster.year) + "-" + String(roster.month).padStart(2, "0") + "-")) { setError("The assignment date must be in the roster month."); return; }
  if (!employees.some(item => item.id === employeeId && item.is_active)) { setError("Select an active employee."); return; }
  if (!eligibility.some(item => item.brand_id === brandId && item.process_id === processId)) { setError("The selected employee is not eligible for that brand and process."); return; }
  setLoading(true);
  try {
   const body = { employee_id: employeeId, assignment_date: date, brand_id: brandId, process_id: processId };
   if (assignment) await rosterService.updateAssignment(roster.id, assignment.id, roster.version, body);
   else await rosterService.addAssignment(roster.id, roster.version, body);
   onSaved();
  } catch (e) { setError(getApiFailure(e).message); }
  finally { setLoading(false); }
 }
 const month = String(roster.month).padStart(2, "0");
 const lastDay = new Date(roster.year, roster.month, 0).getDate();
 return <Dialog open={open} title={assignment ? "Edit working assignment" : "Add working assignment"} onClose={onClose}>
  <form onSubmit={save} className="space-y-3">
   <Field label="Employee" required><Select required value={employeeId} onChange={e => void chooseEmployee(e.target.value)}><option value="">Select active employee</option>{employees.filter(item => item.is_active).map(item => <option key={item.id} value={item.id}>{item.full_name} · {item.employee_id}</option>)}</Select></Field>
   <Field label="Date" required><Input required type="date" min={roster.year + "-" + month + "-01"} max={roster.year + "-" + month + "-" + lastDay} value={date} onChange={e => setDate(e.target.value)}/></Field>
   <Field label="Brand" required><Select required value={brandId} onChange={e => { setBrandId(e.target.value); setProcessId(""); }}><option value="">Select eligible brand</option>{brands.filter(item => eligibility.some(pair => pair.brand_id === item.id)).map(item => <option key={item.id} value={item.id}>{item.brand_name}</option>)}</Select></Field>
   <Field label="Process" required><Select required value={processId} onChange={e => setProcessId(e.target.value)}><option value="">Select eligible process</option>{processes.filter(item => eligibility.some(pair => pair.brand_id === brandId && pair.process_id === item.id)).map(item => <option key={item.id} value={item.id}>{item.process_name}</option>)}</Select></Field>
   {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
   <p className="text-xs text-slate-500">The backend revalidates eligibility, availability, staffing and roster version before committing.</p>
   <SaveBar saving={loading} onCancel={onClose}/>
  </form>
 </Dialog>;
}

export function DeleteAssignmentDialog({ assignment, onClose, onConfirm, busy }: {
 assignment: RosterAssignment | null; onClose: () => void; onConfirm: () => void; busy: boolean;
}) { return <Dialog open={Boolean(assignment)} title="Remove roster assignment?" onClose={onClose}><p className="text-sm text-slate-600">Removing this assignment may create a staffing gap. The backend validates the entire draft before committing the change.</p><div className="mt-5 flex justify-end gap-2"><button onClick={onClose} className="rounded border px-3 py-2 text-sm">Cancel</button><Button disabled={busy} className="bg-rose-700 hover:bg-rose-800" onClick={onConfirm}>{busy ? "Removing…" : "Remove assignment"}</Button></div></Dialog>; }
