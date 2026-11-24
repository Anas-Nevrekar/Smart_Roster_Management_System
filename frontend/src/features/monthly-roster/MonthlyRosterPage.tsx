import { useCallback, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, RefreshCw } from "lucide-react";
import { Badge, EmptyState, ErrorState, Loading } from "../../components/ui/Feedback";
import { Button } from "../../components/ui/Button";
import { PageHeader } from "../../components/ui/PageHeader";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { ConfirmDialog } from "../../components/ui/Dialog";
import { Toast } from "../../components/ui/Toast";
import { useResource } from "../../hooks/useResource";
import { getApiFailure } from "../../lib/api";
import { masterDataService, rosterService } from "../../services/api";
import type { Diagnostic, RosterAssignment, ValidationResult } from "../../types/roster";
import type { BrandRosterGroup, EmployeeRosterGroup, ProcessRosterGroup, RosterView } from "../../types/roster-views";
import { groupsFromAssignments, RosterGrid } from "./RosterGrid";
import { BrandRosterSections, ProcessRosterSections } from "./GroupedRosterSections";
import { CoveragePanel } from "./CoveragePanel";
import { DiagnosticsPanel, ValidationPanel } from "./DiagnosticsPanel";
import { AssignmentEditor, DeleteAssignmentDialog } from "./AssignmentEditor";
import { ChangeImpactDialog } from "./ChangeImpactDialog";

type ViewName = "company" | "pod" | "brand" | "process" | "employee";
type Panel = "roster" | "coverage" | "diagnostics";
const views: { id: ViewName; title: string }[] = [
 { id: "company", title: "Company-wide" }, { id: "pod", title: "Pod-wise" }, { id: "brand", title: "Brand-wise" }, { id: "process", title: "Process-wise" }, { id: "employee", title: "Employee-wise" },
];
const noCoverage = { data: [], summary: { total_requirements: 0, requirements_satisfied: 0, coverage_gaps: 0, total_working_assignments: 0, total_weekly_offs: 0 } };
function flattenView(value: RosterView | null): EmployeeRosterGroup[] {
 if (!value) return [];
 if (value.view === "employee") return value.employees;
 if (value.view === "company" && value.employee_groups) return value.employee_groups;
 if (value.view === "pod") return value.pods.flatMap(item => item.employees);
 if (value.view === "brand") return groupsFromAssignments(value.brands.flatMap(brand => brand.processes.flatMap(process => process.assignments)));
 if (value.view === "process") return groupsFromAssignments(value.processes.flatMap(process => process.brands.flatMap(brand => brand.assignments)));
 return groupsFromAssignments(value.assignments, value.weekly_offs);
}
function showApiError(error: unknown) { const failure = getApiFailure(error); return failure.message; }

export function MonthlyRosterPage() {
 const today = new Date();
 const [month, setMonth] = useState(today.getMonth() + 1);
 const [year, setYear] = useState(today.getFullYear());
 const [revision, setRevision] = useState(0);
 const [viewRevision, setViewRevision] = useState(0);
 const rosterListLoader = useCallback(() => rosterService.list({ month, year }), [month, year, revision]);
 const rosterList = useResource(rosterListLoader);
 const foundRoster = rosterList.loading ? undefined : rosterList.data?.[0];
 const rosterLoader = useCallback(() => foundRoster ? rosterService.get(foundRoster.id) : Promise.resolve(null), [foundRoster?.id, revision]);
 const rosterResource = useResource(rosterLoader);
 const roster = rosterResource.data;
 const [viewName, setViewName] = useState<ViewName>("company");
 const [panel, setPanel] = useState<Panel>("roster");
 const viewLoader = useCallback(() => roster ? rosterService.view<RosterView>(roster.id, viewName) : Promise.resolve(null), [roster?.id, viewName, viewRevision]);
 const viewResource = useResource(viewLoader);
 const rawGroups = useMemo(() => flattenView(viewResource.data), [viewResource.data]);
 const coverageLoader = useCallback(() => roster ? rosterService.coverage(roster.id) : Promise.resolve(noCoverage), [roster?.id, revision]);
 const coverage = useResource(coverageLoader);
 const employees = useResource(masterDataService.employees);
 const pods = useResource(masterDataService.pods);
 const brands = useResource(masterDataService.brands);
 const processes = useResource(masterDataService.processes);
 const leave = useResource(masterDataService.timeOff);
 const holidays = useResource(masterDataService.publicHolidays);
 const [notice, setNotice] = useState<string | null>(null);
 const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
 const [regenerationDiagnostics, setRegenerationDiagnostics] = useState<Diagnostic[]>([]);
 const [validation, setValidation] = useState<ValidationResult | null>(null);
 const [busy, setBusy] = useState(false);
 const [generateConfirm, setGenerateConfirm] = useState(false);
 const [regenerateConfirm, setRegenerateConfirm] = useState(false);
 const [publishConfirm, setPublishConfirm] = useState(false);
 const [search, setSearch] = useState("");
 const [podFilter, setPodFilter] = useState("");
 const [brandFilter, setBrandFilter] = useState("");
 const [processFilter, setProcessFilter] = useState("");
 const [employeeFilter, setEmployeeFilter] = useState("");
 const [statusFilter, setStatusFilter] = useState("");
 const [dateFrom, setDateFrom] = useState("");
 const [dateTo, setDateTo] = useState("");
 const [assignmentEditor, setAssignmentEditor] = useState<{ item: RosterAssignment | null } | null>(null);
 const [deleteTarget, setDeleteTarget] = useState<RosterAssignment | null>(null);
 const [impactOpen, setImpactOpen] = useState(false);
 const summary = roster?.summary && "total_assignments" in roster.summary ? roster.summary : null;
 const canEdit = roster?.status === "draft";
 const canPublish = canEdit && (validation?.valid ?? roster?.latest_validation?.valid ?? false);
 const brandView = viewResource.data?.view === "brand" ? viewResource.data : null;
 const processView = viewResource.data?.view === "process" ? viewResource.data : null;
 const selectedBrand = brandView?.brands.find((item: BrandRosterGroup) => item.brand.brand_id === brandFilter);
 const selectedProcess = processView?.processes.find((item: ProcessRosterGroup) => item.process.process_id === processFilter);
 const monthName = new Date(year, month - 1).toLocaleString(undefined, { month: "long" });
 const yearOptions = Array.from({ length: 13 }, (_, i) => today.getFullYear() - 5 + i);
 const filteredGroups = useMemo(() => rawGroups.map(group => {
  const matchesPerson = (!search || (group.employee_name + " " + group.employee_id).toLowerCase().includes(search.toLowerCase())) && (!podFilter || group.pod_id === podFilter);
  let working = group.assignments.filter(item => (!brandFilter || item.brand_id === brandFilter) && (!processFilter || item.process_id === processFilter) && (!dateFrom || item.assignment_date >= dateFrom) && (!dateTo || item.assignment_date <= dateTo));
  let weeklyOffs = group.weekly_offs.filter(item => (!dateFrom || item.assignment_date >= dateFrom) && (!dateTo || item.assignment_date <= dateTo));
  if (statusFilter === "working") weeklyOffs = [];
  if (statusFilter === "weekly_off") working = [];
  const constrained = Boolean(search || podFilter || brandFilter || processFilter || statusFilter || dateFrom || dateTo);
  return { ...group, assignments: working, weekly_offs: weeklyOffs, matchesPerson, hasResults: !constrained || working.length + weeklyOffs.length > 0 };
 }).filter(group => group.matchesPerson && group.hasResults), [rawGroups, search, podFilter, brandFilter, processFilter, statusFilter, dateFrom, dateTo]);
 const employeeGroups = filteredGroups.filter(group => !employeeFilter || group.employee_id === employeeFilter);
 const groupFilters = { search, podId: podFilter, startDate: dateFrom, endDate: dateTo, status: statusFilter };
 const personMatches = (item: RosterAssignment) => (!search || `${item.employee_name ?? ""} ${item.employee_id}`.toLowerCase().includes(search.trim().toLowerCase()))
  && (!podFilter || item.pod_id === podFilter);
 const assignmentMatches = (item: RosterAssignment) => personMatches(item) && (!dateFrom || item.assignment_date >= dateFrom) && (!dateTo || item.assignment_date <= dateTo);
 const matchedRosterEmployees = (assignments: RosterAssignment[], offs: RosterAssignment[]) => {
  const matched = assignments.filter(assignmentMatches);
  const owners = new Set(assignments.filter(personMatches).map(item => item.employee_id));
  const matchedOffs = offs.filter(item => owners.has(item.employee_id) && (!dateFrom || item.assignment_date >= dateFrom) && (!dateTo || item.assignment_date <= dateTo) && (!podFilter || item.pod_id === podFilter));
  return new Set([...(statusFilter === "weekly_off" ? [] : matched), ...(statusFilter === "working" ? [] : matchedOffs)].map(item => item.employee_id)).size;
 };
 const brandResultCount = selectedBrand ? matchedRosterEmployees(selectedBrand.processes.flatMap(item => item.assignments), selectedBrand.processes.flatMap(item => item.weekly_offs ?? [])) : 0;
 const processResultCount = selectedProcess ? matchedRosterEmployees(selectedProcess.brands.flatMap(item => item.assignments), selectedProcess.brands.flatMap(item => item.weekly_offs ?? [])) : 0;
 const visibleResultCount = viewName === "brand" ? brandResultCount : viewName === "process" ? processResultCount : viewName === "employee" ? employeeGroups.length : filteredGroups.length;

 function reload() { setRevision(value => value + 1); setViewRevision(value => value + 1); setValidation(null); setDiagnostics([]); }
 function moveMonth(delta: number) { const next = new Date(year, month - 1 + delta, 1); setMonth(next.getMonth() + 1); setYear(next.getFullYear()); setPanel("roster"); setValidation(null); setDiagnostics([]); }
 async function generateRoster() {
  setBusy(true); setGenerateConfirm(false); setNotice(null); setDiagnostics([]);
  try {
   const result = await rosterService.generate(month, year);
   if (result.success && result.roster) { setNotice("Draft roster generated and saved."); reload(); }
   else { setDiagnostics(result.diagnostics); setPanel("diagnostics"); setNotice("Generation found conflicts. No draft roster was saved."); }
  } catch (error) { setNotice(showApiError(error)); reload(); }
  finally { setBusy(false); }
 }
 async function regenerateRoster() {
  if (!roster || roster.status !== "draft") return;
  setBusy(true); setRegenerateConfirm(false); setNotice(null); setRegenerationDiagnostics([]);
  try {
   const result = await rosterService.regenerate(roster.id, roster.version);
   if (result.success && result.roster) { setNotice("Draft roster regenerated from the latest master data."); reload(); }
   else { setRegenerationDiagnostics(result.diagnostics); setNotice("Regeneration failed. Your previous saved roster has been preserved."); }
  } catch (error) {
   const failure = getApiFailure(error);
   setNotice(`Regeneration failed. Your previous saved roster has been preserved. ${failure.message}`);
   if (failure.status === 409) { setRevision(value => value + 1); setViewRevision(value => value + 1); setValidation(null); }
  } finally { setBusy(false); }
 }
 async function validateRoster() {
  if (!roster) return;
  setBusy(true);
  try { const result = await rosterService.validate(roster.id); setValidation(result); setDiagnostics(result.errors); setPanel("diagnostics"); setNotice(result.valid ? "Backend validation passed." : "Backend validation found conflicts."); }
  catch (error) { setNotice(showApiError(error)); }
  finally { setBusy(false); }
 }
 async function publishRoster() {
  if (!roster) return;
  setBusy(true);
  try { await rosterService.publish(roster.id); setPublishConfirm(false); setValidation(null); reload(); setNotice("Roster published."); }
  catch (error) { setPublishConfirm(false); setNotice(showApiError(error)); reload(); }
  finally { setBusy(false); }
 }
 async function removeAssignment() {
  if (!roster || !deleteTarget) return;
  setBusy(true);
  try { await rosterService.deleteAssignment(roster.id, deleteTarget.id, roster.version); setDeleteTarget(null); reload(); setNotice("Assignment removed after backend validation."); }
  catch (error) { setDeleteTarget(null); setNotice(showApiError(error)); }
  finally { setBusy(false); }
 }

 return <><PageHeader title="Monthly Roster" description="Generate, inspect, validate and publish workforce schedules." actions={<div className="flex flex-wrap gap-2">{roster ? <><Button disabled={busy} onClick={() => void validateRoster()}>Validate Roster</Button>{canEdit && <Button onClick={() => setImpactOpen(true)}>Change impact</Button>}<Button disabled={busy || !canPublish} onClick={() => setPublishConfirm(true)}>Publish Roster</Button><Button disabled={busy || !canEdit} title={canEdit ? "Replace this draft with a roster generated from current master data" : "Published rosters cannot be regenerated"} onClick={() => setRegenerateConfirm(true)}><RefreshCw size={16}/>Regenerate Roster</Button></> : <Button disabled={busy || rosterList.loading || rosterResource.loading || Boolean(foundRoster)} onClick={() => setGenerateConfirm(true)}>{rosterList.loading || rosterResource.loading ? "Loading roster…" : "Generate Roster"}</Button>}</div>}/>
 <section className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-white p-3">
  <div className="flex items-center gap-2"><button aria-label="Previous month" className="rounded border p-2" onClick={() => moveMonth(-1)}><ChevronLeft size={16}/></button><Select aria-label="Roster month" value={month} onChange={e => { setMonth(Number(e.target.value)); setValidation(null); }} className="w-auto">{Array.from({ length: 12 }, (_, index) => index + 1).map(value => <option key={value} value={value}>{new Date(2000, value - 1).toLocaleString(undefined, { month: "long" })}</option>)}</Select><Select aria-label="Roster year" value={year} onChange={e => { setYear(Number(e.target.value)); setValidation(null); }} className="w-auto">{yearOptions.map(value => <option key={value}>{value}</option>)}</Select><button aria-label="Next month" className="rounded border p-2" onClick={() => moveMonth(1)}><ChevronRight size={16}/></button></div>
  <div className="flex flex-wrap items-center gap-3">{rosterList.loading ? <span className="text-sm text-slate-500">Checking saved roster…</span> : roster ? <><Badge tone={roster.status === "published" ? "green" : "amber"}>{roster.status}</Badge><span className="text-sm text-slate-500">Version {roster.version}</span></> : <Badge>Not generated</Badge>}{roster?.published_at && <span className="text-xs text-slate-500">Published {new Date(roster.published_at).toLocaleString()}</span>}</div>
 </section>
 {notice && <div role="status" className="mb-4 rounded-md border border-indigo-100 bg-indigo-50 p-3 text-sm text-indigo-900">{notice}<button className="ml-3 underline" onClick={() => setNotice(null)}>Dismiss</button></div>}
 {regenerationDiagnostics.length > 0 && <section className="mb-4 rounded-md border border-rose-200 bg-rose-50 p-3"><h2 className="mb-2 font-semibold text-rose-900">Latest regeneration attempt diagnostics</h2><DiagnosticsPanel diagnostics={regenerationDiagnostics}/></section>}
 {roster?.master_data_stale === true && <div role="status" className="mb-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">Master data has changed since this roster was generated. Regeneration is recommended.</div>}
 {roster?.master_data_stale === null && <div role="status" className="mb-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">This roster predates master-data change tracking, so its freshness cannot be determined.</div>}
 {rosterList.error || rosterResource.error ? <ErrorState message={rosterList.error ?? rosterResource.error ?? "The roster could not be loaded."} retry={() => { void rosterList.retry(); setRevision(value => value + 1); }}/> : rosterList.loading || rosterResource.loading ? <Loading label={"Loading " + monthName + " " + year + " roster"}/> : !roster ? <><EmptyState title={"No roster for " + monthName + " " + year}>Generation saves a draft only when scheduling and independent validation both succeed.</EmptyState>{diagnostics.length > 0 && <section className="mt-5"><h2 className="mb-2 font-semibold">Generation diagnostics</h2><DiagnosticsPanel diagnostics={diagnostics}/></section>}</> : <>
  <section className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">{[
   ["Employees", employees.data?.length ?? 0], ["Active employees", summary?.active_employees ?? 0], ["Brands", summary?.active_brands ?? 0], ["Processes", summary?.active_processes ?? 0], ["Working assignments", summary?.total_assignments ?? roster.assignment_count], ["Weekly offs", summary?.total_weekly_offs ?? roster.weekly_off_count], ["Coverage gaps", coverage.data?.summary.coverage_gaps ?? summary?.coverage_gaps ?? 0],
  ].map(([label, value]) => <div key={label} className="rounded-md border border-slate-200 bg-white p-3"><div className="text-xs text-slate-500">{label}</div><div className={"mt-1 text-xl font-semibold " + (label === "Coverage gaps" && Number(value) > 0 ? "text-rose-700" : "")}>{value}</div></div>)}</section>
  <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200"><div className="flex gap-1 overflow-x-auto" role="tablist" aria-label="Roster panels">{(["roster", "coverage", "diagnostics"] as const).map(value => <button key={value} role="tab" aria-selected={panel === value} onClick={() => setPanel(value)} className={"border-b-2 px-3 py-2 text-sm font-medium " + (panel === value ? "border-indigo-700 text-indigo-800" : "border-transparent text-slate-500")}>{value === "roster" ? "Roster views" : value === "coverage" ? "Coverage" : "Conflicts & Diagnostics"}</button>)}</div>{panel === "roster" && canEdit && <Button onClick={() => setAssignmentEditor({ item: null })}><Plus size={16}/>Add assignment</Button>}</div>
  {panel === "roster" && <><div className="mb-3 flex gap-1 overflow-x-auto" role="tablist" aria-label="Roster views">{views.map(value => <button key={value.id} role="tab" aria-selected={viewName === value.id} onClick={() => setViewName(value.id)} className={"rounded-t px-3 py-2 text-sm " + (viewName === value.id ? "bg-indigo-50 font-medium text-indigo-800" : "text-slate-600 hover:bg-slate-100")}>{value.title}</button>)}</div>
   <div className="mb-4 flex flex-wrap items-center gap-2">
    <Input aria-label="Search employee" placeholder="Search name or ID" value={search} onChange={e => setSearch(e.target.value)} className="w-48"/>
    {viewName === "brand" ? <><Select aria-label="Brand-wise brand selector" value={brandFilter} onChange={e => { setBrandFilter(e.target.value); setProcessFilter(""); }} className="w-auto"><option value="">Select a brand</option>{brands.data?.map(item => <option key={item.id} value={item.id}>{item.brand_name}</option>)}</Select><Select aria-label="Brand-wise process selector" value={processFilter} onChange={e => setProcessFilter(e.target.value)} className="w-auto"><option value="">All processes</option>{selectedBrand?.processes.map(item => <option key={item.process.process_id} value={item.process.process_id}>{item.process.process_name}</option>)}</Select></> : viewName === "process" ? <><Select aria-label="Process-wise process selector" value={processFilter} onChange={e => { setProcessFilter(e.target.value); setBrandFilter(""); }} className="w-auto"><option value="">Select a process</option>{processView?.processes.map(item => <option key={item.process.process_id} value={item.process.process_id}>{item.process.process_name}</option>) ?? processes.data?.map(item => <option key={item.id} value={item.process_id}>{item.process_name}</option>)}</Select><Select aria-label="Process-wise brand selector" value={brandFilter} onChange={e => setBrandFilter(e.target.value)} className="w-auto"><option value="">All brands</option>{selectedProcess?.brands.map(item => <option key={item.brand.brand_id} value={item.brand.brand_id}>{item.brand.brand_name}</option>)}</Select></> : viewName === "employee" ? <Select aria-label="Employee-wise employee selector" value={employeeFilter} onChange={e => setEmployeeFilter(e.target.value)} className="w-auto"><option value="">Select an employee</option>{employees.data?.filter(item => item.is_active).map(item => <option key={item.employee_id} value={item.employee_id}>{item.full_name} · {item.employee_id}</option>)}</Select> : <><Select aria-label="Roster brand filter" value={brandFilter} onChange={e => setBrandFilter(e.target.value)} className="w-auto"><option value="">All brands</option>{brands.data?.map(item => <option key={item.id} value={item.id}>{item.brand_name}</option>)}</Select><Select aria-label="Roster process filter" value={processFilter} onChange={e => setProcessFilter(e.target.value)} className="w-auto"><option value="">All processes</option>{processes.data?.map(item => <option key={item.id} value={item.id}>{item.process_name}</option>)}</Select></>}
    <Select aria-label="Roster pod filter" value={podFilter} onChange={e => setPodFilter(e.target.value)} className="w-auto"><option value="">All pods</option>{pods.data?.map(item => <option key={item.id} value={item.id}>{item.pod_name}</option>)}</Select>
    <Select aria-label="Assignment status filter" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="w-auto"><option value="">All statuses</option><option value="working">Working</option><option value="weekly_off">Weekly off</option></Select><Input aria-label="Roster date from" type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-auto"/><Input aria-label="Roster date to" type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="w-auto"/><button className="text-sm text-indigo-700 underline" onClick={() => { setSearch(""); setPodFilter(""); setBrandFilter(""); setProcessFilter(""); setEmployeeFilter(""); setStatusFilter(""); setDateFrom(""); setDateTo(""); }}>Clear filters</button><span className="text-xs text-slate-500">{visibleResultCount} employees</span>
   </div>
   {viewResource.loading ? <Loading label="Loading roster view"/> : viewResource.error ? <ErrorState message={viewResource.error} retry={() => void viewResource.retry()}/> : viewName === "brand" ? !brandFilter ? <EmptyState title="Select a brand to inspect its roster."/> : selectedBrand ? <BrandRosterSections group={selectedBrand} processId={processFilter} filters={groupFilters} month={month} year={year} leaves={leave.data ?? []} holidays={holidays.data ?? []} coverage={coverage.data?.data ?? []} editable={canEdit} onEdit={item => setAssignmentEditor({ item })} onDelete={item => setDeleteTarget(item)}/> : <EmptyState title="No configured processes or assignments for this brand."/> : viewName === "process" ? !processFilter ? <EmptyState title="Select a process to inspect its roster."/> : selectedProcess ? <ProcessRosterSections group={selectedProcess} brandId={brandFilter} filters={groupFilters} month={month} year={year} leaves={leave.data ?? []} holidays={holidays.data ?? []} coverage={coverage.data?.data ?? []} editable={canEdit} onEdit={item => setAssignmentEditor({ item })} onDelete={item => setDeleteTarget(item)}/> : <EmptyState title="No configured brands for this process."/> : viewName === "employee" && !employeeFilter ? <EmptyState title="Select an employee to inspect their roster."/> : employeeGroups.length === 0 ? <EmptyState title="No roster entries match these filters."/> : <><div className="mb-2 flex flex-wrap gap-3 text-xs text-slate-600"><span>Indigo: working</span><span>WO: weekly off</span><span>Amber: leave</span><span>Warning: relevant coverage gap</span></div><RosterGrid groups={employeeGroups} month={month} year={year} leaves={leave.data ?? []} holidays={holidays.data ?? []} coverage={(coverage.data?.data ?? []).filter(row => (!brandFilter || row.brand_id === brandFilter) && (!processFilter || row.process_id === processFilter) && (!dateFrom || row.date >= dateFrom) && (!dateTo || row.date <= dateTo))} editable={canEdit} onEdit={item => setAssignmentEditor({ item })} onDelete={item => setDeleteTarget(item)}/></>}</>}
  {panel === "coverage" && (coverage.loading ? <Loading label="Loading coverage"/> : coverage.error ? <ErrorState message={coverage.error} retry={() => void coverage.retry()}/> : <CoveragePanel rows={coverage.data?.data ?? []} summary={coverage.data?.summary ?? noCoverage.summary} brands={brands.data ?? []} processes={processes.data ?? []} onInspect={row => { setBrandFilter(row.brand_id); setProcessFilter(row.process_id); setPanel("roster"); setViewName("brand"); }}/>)}
  {panel === "diagnostics" && <><div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold">Conflicts & Diagnostics</h2><p className="text-xs text-slate-500">Diagnostics are returned by backend generation and validation.</p></div><Button className="bg-white text-slate-800 ring-1 ring-slate-300 hover:bg-slate-50" disabled={busy} onClick={() => void validateRoster()}>Validate now</Button></div>{validation ? <ValidationPanel result={validation}/> : <DiagnosticsPanel diagnostics={diagnostics.length ? diagnostics : roster.latest_validation?.errors ?? []}/>}</>}
  <footer className="mt-4 text-xs text-slate-500">Validation: {validation?.valid ? "Valid" : validation ? "Invalid" : roster.latest_validation?.valid ? "Valid" : roster.latest_validation ? "Invalid" : "Not validated"} · {validation?.validated_at ? new Date(validation.validated_at).toLocaleString() : roster.latest_validation?.validated_at ? new Date(roster.latest_validation.validated_at).toLocaleString() : "No timestamp"}</footer>
 </>}
 <ConfirmDialog open={generateConfirm} title={"Generate " + monthName + " " + year + " roster?"} message="Generation creates a saved draft only when the backend reports successful scheduling and validation. Existing rosters cannot be generated again." onCancel={() => setGenerateConfirm(false)} onConfirm={() => void generateRoster()}/>
 <ConfirmDialog open={regenerateConfirm} title={`Regenerate ${monthName} ${year} roster?`} message={`Current roster version: ${roster?.version ?? "—"}\nCurrent working assignments: ${roster?.assignment_count ?? 0}\nCurrent coverage gaps: ${coverage.data?.summary.coverage_gaps ?? summary?.coverage_gaps ?? "not available"}\n\nRegenerating this roster replaces the draft assignments and weekly offs using current employee availability, eligibility, approved leave, operating rules and public holidays. Any manual changes will be lost. If generation fails, the existing saved draft will be preserved.`} confirmLabel="Confirm Regeneration" disabled={busy} onCancel={() => setRegenerateConfirm(false)} onConfirm={() => void regenerateRoster()}/>
 <ConfirmDialog open={publishConfirm} title="Publish roster?" message="Publishing finalizes the draft. The backend validates again before publishing, and editing is disabled afterward." onCancel={() => setPublishConfirm(false)} onConfirm={() => void publishRoster()}/>
 {roster && <AssignmentEditor open={assignmentEditor !== null} roster={roster} assignment={assignmentEditor?.item ?? null} employees={employees.data ?? []} brands={brands.data ?? []} processes={processes.data ?? []} onClose={() => setAssignmentEditor(null)} onSaved={() => { setAssignmentEditor(null); reload(); setNotice("Assignment saved after backend validation."); }}/>}<DeleteAssignmentDialog assignment={deleteTarget} onClose={() => setDeleteTarget(null)} onConfirm={() => void removeAssignment()} busy={busy}/>
 {roster && <ChangeImpactDialog open={impactOpen} roster={roster} employees={employees.data ?? []} brands={brands.data ?? []} processes={processes.data ?? []} onClose={() => setImpactOpen(false)}/>}
 <Toast message={notice} onDismiss={() => setNotice(null)}/>
 </>;
}
