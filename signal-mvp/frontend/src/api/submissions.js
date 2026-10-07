import { request } from "./client.js";

export function listSubmissions({ page = 1, page_size = 100 } = {}) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(page_size),
  });
  return request(`/api/submissions?${query.toString()}`);
}
