import { request } from "./client";
const getDashboardSummary = () => request("/api/dashboard/summary");
const getDashboardWorkItems = () => request("/api/dashboard/work-items");
const getHealth = () => request("/health");
export {
  getDashboardSummary,
  getDashboardWorkItems,
  getHealth
};