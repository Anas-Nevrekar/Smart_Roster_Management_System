import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Sidebar } from "../components/layout/Sidebar";
import { Loading, ErrorState } from "../components/ui/Feedback";
import { api, API_BASE_URL, getApiFailure } from "../lib/api";
import { AppLayout } from "../components/layout/AppLayout";
import { healthService, masterDataService } from "../services/api";
afterEach(cleanup);
describe("frontend foundation", () => {
 it("shows seven sidebar sections and navigates to a selected route", async () => {
   render(<MemoryRouter initialEntries={["/rosters"]}><Sidebar/><Routes><Route path="/employees" element={<p>Employees page</p>}/><Route path="/rosters" element={<p>Roster page</p>}/></Routes></MemoryRouter>);
   expect(screen.getByRole("navigation", { name: "Main navigation" }).querySelectorAll("a")).toHaveLength(7);
   await userEvent.click(screen.getByRole("link", { name: "Employees" })); expect(await screen.findByText("Employees page")).toBeInTheDocument();
 });
 it("renders the shared responsive shell and unknown-route fallback content", async () => {
   const mock = vi.spyOn(healthService, "health").mockResolvedValue({ status: "ok", application: "Smart Roster", version: "1" });
   render(<MemoryRouter initialEntries={["/missing"]}><Routes><Route element={<AppLayout/>}><Route path="*" element={<p>Page not found</p>}/></Route></Routes></MemoryRouter>);
   expect(await screen.findByText("Page not found")).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Open navigation" })).toBeInTheDocument(); mock.mockRestore();
 });
 it("uses the configured API base URL and unwraps health response", async () => {
   expect(API_BASE_URL).toBe(import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1");
   const request = vi.spyOn(api, "get").mockResolvedValue({ data: { success: true, data: { status: "ok", application: "Smart Roster", version: "1" } } });
   await expect(healthService.health()).resolves.toMatchObject({ status: "ok" }); expect(request).toHaveBeenCalledWith("/health"); request.mockRestore();
 });
 it("normalizes API failures and requests master data from the versioned API", async () => {
   expect(getApiFailure({ code: "NOT_FOUND", message: "Missing", status: 404 })).toMatchObject({ code: "NOT_FOUND", status: 404 });
   const request = vi.spyOn(api, "get").mockResolvedValue({ data: { success: true, data: [], total: 0 } });
   await masterDataService.employees(); await masterDataService.pods(); await masterDataService.brands(); await masterDataService.processes();
   await masterDataService.operatingRules(); await masterDataService.timeOff(); await masterDataService.publicHolidays();
   expect(request.mock.calls.map(([url]) => url)).toEqual(["/employees", "/pods", "/brands", "/processes", "/operating-rules", "/time-off", "/public-holidays"]); request.mockRestore();
 });
 it("renders loading and retryable error feedback", async () => {
   const retry = vi.fn(); render(<><Loading/><ErrorState message="Unable to reach API" retry={retry}/></>);
   expect(screen.getByRole("status")).toHaveTextContent("Loading"); expect(screen.getByRole("alert")).toHaveTextContent("Unable to reach API");
   await userEvent.click(screen.getByRole("button", { name: /retry/i })); await waitFor(() => expect(retry).toHaveBeenCalledOnce());
 });
});
