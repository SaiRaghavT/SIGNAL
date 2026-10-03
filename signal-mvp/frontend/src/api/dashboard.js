import { request } from "./client";
const getDashboardSummary = () => request("/api/dashboard/summary");
const getHealth = () => request("/health");
export {
  getDashboardSummary,
  getHealth
};
