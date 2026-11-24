import { NavLink } from "react-router-dom";
import { CalendarDays, Users, Tags, Boxes, Palmtree, Settings2, CalendarCheck } from "lucide-react";
const links = [
  ["Monthly Roster", "/rosters", CalendarDays], ["Employees", "/employees", Users], ["Brands & Processes", "/brands-processes", Tags],
  ["Pods", "/pods", Boxes], ["Leave & Availability", "/leave-availability", Palmtree], ["Operating Rules", "/operating-rules", Settings2], ["Public Holidays", "/public-holidays", CalendarCheck],
] as const;
export function Sidebar({ close }: { close?: () => void }) { return <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white"><div className="flex h-16 items-center border-b border-slate-200 px-6"><span className="text-lg font-semibold tracking-tight text-slate-900">Smart Roster</span></div><nav aria-label="Main navigation" className="space-y-1 p-3">{links.map(([label, href, Icon]) => <NavLink key={href} to={href} onClick={close} className={({ isActive }) => `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium ${isActive ? "bg-indigo-50 text-indigo-800" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}><Icon size={18}/>{label}</NavLink>)}</nav></aside>; }
