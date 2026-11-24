import type { BrandRosterGroup, ProcessRosterGroup } from "../../types/roster-views";
import type { CoverageRow, RosterAssignment } from "../../types/roster";
import type { PublicHoliday, TimeOff } from "../../types/master-data";
import { Badge, EmptyState } from "../../components/ui/Feedback";
import { RosterGrid, groupsFromAssignments } from "./RosterGrid";

export interface RosterGroupFilters {
 search: string;
 podId: string;
 startDate: string;
 endDate: string;
 status: string;
}

function matchingPeople(item: RosterAssignment, filters: RosterGroupFilters) {
 const query = filters.search.trim().toLowerCase();
 return (!query || `${item.employee_name ?? ""} ${item.employee_id}`.toLowerCase().includes(query))
  && (!filters.podId || item.pod_id === filters.podId);
}
function inDateRange(item: RosterAssignment, filters: RosterGroupFilters) {
 return (!filters.startDate || item.assignment_date >= filters.startDate)
  && (!filters.endDate || item.assignment_date <= filters.endDate);
}
function coverageInRange(rows: CoverageRow[], filters: RosterGroupFilters) {
 return rows.filter(row => (!filters.startDate || row.date >= filters.startDate) && (!filters.endDate || row.date <= filters.endDate));
}
function CoverageTable({ rows }: { rows: CoverageRow[] }) {
 return rows.length === 0 ? <p className="text-xs text-slate-500">No coverage rows for this date range.</p> : <div className="overflow-x-auto rounded border border-slate-200"><table className="min-w-full text-xs"><thead className="bg-slate-50 text-left"><tr>{["Date", "Required", "Actual", "Gap", "Status"].map(title => <th key={title} className="px-3 py-2">{title}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={`${row.date}-${row.brand_id}-${row.process_id}`} className="border-t"><td className="px-3 py-2">{row.date}</td><td className="px-3 py-2">{row.required_staffing ?? "—"}</td><td className="px-3 py-2">{row.actual_staffing}</td><td className="px-3 py-2">{row.staffing_gap}</td><td className="px-3 py-2"><Badge tone={row.status === "understaffed" ? "red" : row.status === "satisfied" ? "green" : "neutral"}>{row.status.replace("_", " ")}</Badge></td></tr>)}</tbody></table></div>;
}
function AssignmentRoster({ assignments, weeklyOffs, filters, month, year, leaves, holidays, coverage, editable, onEdit, onDelete }: {
 assignments: RosterAssignment[]; weeklyOffs: RosterAssignment[]; filters: RosterGroupFilters; month: number; year: number;
 leaves: TimeOff[]; holidays: PublicHoliday[]; coverage: CoverageRow[]; editable: boolean;
 onEdit: (assignment: RosterAssignment) => void; onDelete: (assignment: RosterAssignment) => void;
}) {
 const people = assignments.filter(item => matchingPeople(item, filters) && inDateRange(item, filters));
 const owners = new Set(assignments.filter(item => matchingPeople(item, filters)).map(item => item.employee_id));
 const offs = weeklyOffs.filter(item => owners.has(item.employee_id) && matchingPeople(item, filters) && inDateRange(item, filters));
 const visibleAssignments = filters.status === "weekly_off" ? [] : people;
 const visibleOffs = filters.status === "working" ? [] : offs;
 const groups = groupsFromAssignments(visibleAssignments, visibleOffs);
 return groups.length ? <RosterGrid groups={groups} month={month} year={year} leaves={leaves} holidays={holidays} coverage={coverage} editable={editable} onEdit={onEdit} onDelete={onDelete}/> : <EmptyState title="No assigned employees match these filters."/>;
}

export function BrandRosterSections({ group, processId, filters, month, year, leaves, holidays, coverage, editable, onEdit, onDelete }: {
 group: BrandRosterGroup; processId: string; filters: RosterGroupFilters; month: number; year: number; leaves: TimeOff[];
 holidays: PublicHoliday[]; coverage: CoverageRow[]; editable: boolean; onEdit: (assignment: RosterAssignment) => void; onDelete: (assignment: RosterAssignment) => void;
}) {
 const processes = group.processes.filter(item => !processId || item.process.process_id === processId);
 const visibleCoverage = coverage.filter(row => row.brand_id === group.brand.brand_id && (!processId || row.process_id === processId));
 const employees = new Set(processes.flatMap(item => item.assignments.filter(row => matchingPeople(row, filters) && inDateRange(row, filters)).map(row => row.employee_id)));
 const gaps = coverageInRange(visibleCoverage, filters).filter(row => row.status === "understaffed").length;
 return <section className="space-y-5" aria-label={`${group.brand.brand_name} roster`}>
  <div className="rounded-md border border-slate-200 bg-white p-4"><h2 className="text-xl font-semibold">{group.brand.brand_name}</h2><div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3"><div><div className="text-xs text-slate-500">Configured processes</div><div className="font-semibold">{group.processes.length}</div></div><div><div className="text-xs text-slate-500">Assigned employees</div><div className="font-semibold">{employees.size}</div></div><div><div className="text-xs text-slate-500">Coverage gaps</div><div className="font-semibold">{gaps}</div></div></div></div>
  {processes.map(process => {
   const rows = visibleCoverage.filter(row => row.process_id === process.process.process_id);
   return <section key={process.process.process_id} className="space-y-2 rounded-md border border-slate-200 bg-white p-4" aria-label={`${process.process.process_name} process roster`}>
    <div><h3 className="text-base font-semibold">{process.process.process_name}</h3><p className="text-xs text-slate-500">{new Set(process.assignments.filter(row => matchingPeople(row, filters) && inDateRange(row, filters)).map(row => row.employee_id)).size} assigned employees · {coverageInRange(rows, filters).filter(row => row.status === "understaffed").length} coverage gaps</p></div>
    <CoverageTable rows={coverageInRange(rows, filters)}/>
    {process.assignments.length ? <AssignmentRoster assignments={process.assignments} weeklyOffs={process.weekly_offs ?? []} filters={filters} month={month} year={year} leaves={leaves} holidays={holidays} coverage={coverageInRange(rows, filters)} editable={editable} onEdit={onEdit} onDelete={onDelete}/> : <EmptyState title="No working assignments for this process."/>}
   </section>;
  })}
 </section>;
}

export function ProcessRosterSections({ group, brandId, filters, month, year, leaves, holidays, coverage, editable, onEdit, onDelete }: {
 group: ProcessRosterGroup; brandId: string; filters: RosterGroupFilters; month: number; year: number; leaves: TimeOff[];
 holidays: PublicHoliday[]; coverage: CoverageRow[]; editable: boolean; onEdit: (assignment: RosterAssignment) => void; onDelete: (assignment: RosterAssignment) => void;
}) {
 const brands = group.brands.filter(item => !brandId || item.brand.brand_id === brandId);
 return <section className="space-y-5" aria-label={`${group.process.process_name} roster`}>
  <h2 className="text-xl font-semibold">{group.process.process_name}</h2>
  {brands.map(brand => {
   const rows = coverage.filter(row => row.process_id === group.process.process_id && row.brand_id === brand.brand.brand_id);
   return <section key={brand.brand.brand_id} className="space-y-2 rounded-md border border-slate-200 bg-white p-4" aria-label={`${brand.brand.brand_name} assignments`}>
    <h3 className="text-base font-semibold">{brand.brand.brand_name}</h3><CoverageTable rows={coverageInRange(rows, filters)}/>
    {brand.assignments.length ? <AssignmentRoster assignments={brand.assignments} weeklyOffs={brand.weekly_offs ?? []} filters={filters} month={month} year={year} leaves={leaves} holidays={holidays} coverage={coverageInRange(rows, filters)} editable={editable} onEdit={onEdit} onDelete={onDelete}/> : <EmptyState title="No working assignments for this brand and process."/>}
   </section>;
  })}
 </section>;
}
