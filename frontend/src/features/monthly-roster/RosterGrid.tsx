import type { EmployeeRosterGroup } from "../../types/roster-views";
import type { CoverageRow, RosterAssignment } from "../../types/roster";
import type { PublicHoliday, TimeOff } from "../../types/master-data";
import { Badge } from "../../components/ui/Feedback";

export function groupsFromAssignments(assignments: RosterAssignment[], weeklyOffs: RosterAssignment[] = []): EmployeeRosterGroup[] {
 const grouped = new Map<string, EmployeeRosterGroup>();
 for (const item of [...assignments, ...weeklyOffs]) {
  const row = grouped.get(item.employee_id) ?? { employee_id: item.employee_id, employee_name: item.employee_name, pod_id: item.pod_id, pod_name: item.pod_name, assignments: [], weekly_offs: [] };
  (item.status === "weekly_off" ? row.weekly_offs : row.assignments).push(item);
  grouped.set(item.employee_id, row);
 }
 return Array.from(grouped.values()).sort((a, b) => (a.employee_name ?? a.employee_id).localeCompare(b.employee_name ?? b.employee_id));
}

function dayRows(assignments: RosterAssignment[], offs: RosterAssignment[], date: string, leaves: TimeOff[], holidays: PublicHoliday[], gaps: CoverageRow[]) {
 const work = assignments.filter(x => x.assignment_date === date); const off = offs.some(x => x.assignment_date === date);
 const dateLeaves = leaves.filter(x => x.start_date <= date && x.end_date >= date);
 const dateHoliday = holidays.find(x => x.holiday_date === date);
 const dayGaps = gaps.filter(x => x.date === date && x.status === "understaffed");
 const dayCoverage = gaps.filter(x => x.date === date);
 const notOperating = dayCoverage.length > 0 && dayCoverage.every(x => x.status === "not_operating");
 return { work, off, dateLeaves, dateHoliday, dayGaps, notOperating };
}
export function RosterGrid({ groups, month, year, leaves, holidays, coverage, editable, onEdit, onDelete }: {
 groups: EmployeeRosterGroup[]; month: number; year: number; leaves: TimeOff[]; holidays: PublicHoliday[]; coverage: CoverageRow[]; editable: boolean;
 onEdit: (assignment: RosterAssignment) => void; onDelete: (assignment: RosterAssignment) => void;
}) {
 const daysInMonth = new Date(year, month, 0).getDate(); const dates = Array.from({ length: daysInMonth }, (_, i) => `${year}-${String(month).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`);
 return <div className="overflow-auto rounded-md border border-slate-200 bg-white max-h-[68vh]"><table className="min-w-max border-separate border-spacing-0 text-xs"><thead className="sticky top-0 z-10 bg-slate-50"><tr><th className="sticky left-0 z-20 min-w-44 border-b border-r bg-slate-50 px-3 py-3 text-left">Employee</th><th className="sticky left-44 z-20 min-w-24 border-b border-r bg-slate-50 px-3 py-3 text-left">ID</th><th className="sticky left-[17rem] z-20 min-w-32 border-b border-r bg-slate-50 px-3 py-3 text-left">Pod</th>{dates.map((date, index) => <th key={date} className="min-w-36 border-b border-r px-2 py-3 text-left"><span className="block font-semibold">{index + 1}</span><span className="text-[10px] font-normal text-slate-500">{new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { weekday: "short" })}</span></th>)}</tr></thead><tbody>{groups.map(group => <tr key={group.employee_id}><th scope="row" className="sticky left-0 z-[1] border-b border-r bg-white px-3 py-2 text-left font-medium">{group.employee_name ?? group.employee_id}</th><td className="sticky left-44 z-[1] border-b border-r bg-white px-3 py-2">{group.employee_id}</td><td className="sticky left-[17rem] z-[1] border-b border-r bg-white px-3 py-2">{group.pod_name ?? "Unassigned"}</td>{dates.map(date => {
 const { work, off, dateLeaves, dateHoliday, dayGaps, notOperating } = dayRows(group.assignments, group.weekly_offs, date, leaves.filter(x => x.employee_id === group.employee_id), holidays, coverage);
 return <td key={date} className={`border-b border-r p-1.5 align-top ${dayGaps.length ? "bg-rose-50" : ""}`}><div className="flex min-h-10 flex-col gap-1">{work.map(a => <div key={a.id} className="group/chip relative rounded border border-indigo-100 bg-indigo-50 px-1.5 py-1 text-indigo-900" title={`${a.brand_name ?? a.brand_id} / ${a.process_name ?? a.process_id}`}><span className="block max-w-36 truncate">{a.brand_name ?? a.brand_id}</span><span className="block max-w-36 truncate text-[10px]">{a.process_name ?? a.process_id}</span>{editable && <span className="mt-1 flex gap-2"><button onClick={() => onEdit(a)} className="underline">Edit</button><button onClick={() => onDelete(a)} className="underline">Delete</button></span>}</div>)}{off && <Badge tone="neutral">WO · Weekly Off</Badge>}{dateLeaves.map(leave => <Badge key={leave.id} tone={leave.status === "approved" ? "amber" : "neutral"}>{leave.status === "approved" ? "Approved leave" : `${leave.status} leave`}</Badge>)}{dateHoliday && <span className="text-[10px] font-medium text-slate-600" title={dateHoliday.holiday_name}>Holiday · {dateHoliday.holiday_name}</span>}{dayGaps.map(gap => <span key={`${gap.brand_id}-${gap.process_id}`} className="font-semibold text-rose-800" title={`${gap.brand_name} / ${gap.process_name}: ${gap.actual_staffing} of ${gap.required_staffing} staff`}>⚠ Gap · {gap.brand_name}</span>)}{work.length === 0 && !off && dateLeaves.length === 0 && !dateHoliday && dayGaps.length === 0 && (notOperating ? <span className="text-[10px] text-slate-500">Not operating</span> : <span className="text-slate-300">—</span>)}</div></td>;
 })}</tr>)}</tbody></table></div>;
}
