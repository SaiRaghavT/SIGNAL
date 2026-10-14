import { request } from "./client";
const getDashboardSummary = (options = {}) => request("/api/dashboard/summary", options);
const getDashboardWorkItems = () => request("/api/dashboard/work-items");
const getHealth = () => request("/health");
export {
  getDashboardSummary,
  getDashboardWorkItems,
  getHealth
};
