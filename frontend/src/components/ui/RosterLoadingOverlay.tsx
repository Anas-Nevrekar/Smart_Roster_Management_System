import { LoaderCircle, Sparkles } from "lucide-react";

export function RosterLoadingOverlay({ action, monthName, year }: {
 action: "generate" | "regenerate" | null;
 monthName: string;
 year: number;
}) {
 if (!action) return null;
 const regenerating = action === "regenerate";

 return <div className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/35 p-4 backdrop-blur-[2px]" aria-live="polite">
  <section role="status" aria-busy="true" aria-label={regenerating ? "Regenerating roster" : "Generating roster"} className="w-full max-w-lg rounded-2xl border border-white/70 bg-white p-6 shadow-2xl shadow-slate-950/20 sm:p-8">
   <div className="flex items-start gap-4">
    <div className="relative grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-indigo-50 text-indigo-700">
     <span className="absolute inset-0 rounded-2xl bg-indigo-200/50 motion-safe:animate-ping"/>
     {regenerating ? <LoaderCircle className="relative motion-safe:animate-spin" size={28}/> : <Sparkles className="relative motion-safe:animate-pulse" size={28}/>}
    </div>
    <div className="min-w-0 pt-0.5">
     <p className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-700">Smart Roster scheduler</p>
     <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">{regenerating ? "Refreshing your roster" : "Building your roster"}</h2>
     <p className="mt-1 text-sm text-slate-500">{monthName} {year}</p>
    </div>
   </div>
   <p className="mt-6 text-sm leading-6 text-slate-700">The scheduler is checking employee availability, weekly offs, and coverage before validating the draft. This may take a few minutes; keep this page open.</p>
   <div className="mt-6 h-2 overflow-hidden rounded-full bg-indigo-100"><div className="roster-progress h-full w-1/3 rounded-full bg-gradient-to-r from-indigo-500 via-violet-600 to-indigo-500"/></div>
   <div className="mt-3 flex items-center gap-2 text-xs font-medium text-slate-500"><LoaderCircle className="motion-safe:animate-spin" size={14}/>Working on a valid schedule…</div>
  </section>
 </div>;
}
