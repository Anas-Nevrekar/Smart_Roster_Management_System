import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { EmployeesPage } from "../features/management/EmployeesPage";
import { BrandsProcessesPage } from "../features/management/BrandsProcessesPage";
import { PodsPage } from "../features/management/PodsPage";
import { LeaveAvailabilityPage } from "../features/management/LeaveAvailabilityPage";
import { OperatingRulesPage } from "../features/management/OperatingRulesPage";
import { PublicHolidaysPage } from "../features/management/PublicHolidaysPage";
import { MonthlyRosterPage } from "../features/monthly-roster/MonthlyRosterPage";
function NotFound() { return <section><h1 className="text-2xl font-semibold">Page not found</h1><p className="mt-2 text-slate-600">That page does not exist. Use the navigation to choose a section.</p></section>; }
export const router = createBrowserRouter([{ path: "/", element: <AppLayout/>, children: [
 { index: true, element: <Navigate to="/rosters" replace/> }, { path: "rosters", element: <MonthlyRosterPage/> }, { path: "employees", element: <EmployeesPage/> },
 { path: "brands-processes", element: <BrandsProcessesPage/> }, { path: "pods", element: <PodsPage/> }, { path: "leave-availability", element: <LeaveAvailabilityPage/> }, { path: "operating-rules", element: <OperatingRulesPage/> }, { path: "public-holidays", element: <PublicHolidaysPage/> }, { path: "*", element: <NotFound/> },
]}]);
