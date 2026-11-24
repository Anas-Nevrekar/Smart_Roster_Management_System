import { useEffect } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";

export function Toast({ message, onDismiss, tone = "success" }: { message: string | null; onDismiss: () => void; tone?: "success" | "error" }) {
 useEffect(() => {
  if (!message) return;
  const timer = window.setTimeout(onDismiss, 7000);
  return () => window.clearTimeout(timer);
 }, [message, onDismiss]);

 if (!message) return null;
 const isError = tone === "error";
 const Icon = isError ? AlertCircle : CheckCircle2;

 return <div className="pointer-events-none fixed inset-x-0 top-5 z-[100] flex justify-center px-4" aria-live="polite">
  <section role={isError ? "alert" : "status"} className={`toast-enter pointer-events-auto w-full max-w-2xl overflow-hidden rounded-xl border bg-white shadow-2xl ring-1 ${isError ? "border-rose-200 ring-rose-950/5" : "border-emerald-200 ring-emerald-950/5"}`}>
   <div className="flex items-start gap-4 px-5 py-4 sm:px-6">
    <span className={`mt-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-full ${isError ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"}`}><Icon size={22}/></span>
    <div className="min-w-0 flex-1">
     <p className={`text-sm font-semibold ${isError ? "text-rose-950" : "text-emerald-950"}`}>{isError ? "Action needs attention" : "Update complete"}</p>
     <p className="mt-1 text-sm leading-6 text-slate-700">{message}</p>
    </div>
    <button type="button" aria-label="Dismiss notification" onClick={onDismiss} className="rounded-md p-1 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"><X size={18}/></button>
   </div>
   <div className={`h-1 ${isError ? "bg-rose-100" : "bg-emerald-100"}`}><div className={`toast-progress h-full w-full ${isError ? "bg-rose-600" : "bg-emerald-600"}`}/></div>
  </section>
 </div>;
}
