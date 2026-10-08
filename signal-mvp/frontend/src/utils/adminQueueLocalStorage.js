const ADMIN_QUEUE_STORAGE_KEY = "signal-admin-queue";
export const ADMIN_QUEUE_UPDATED_EVENT = "signal-admin-queue-updated";

export function getAdminQueueEntries() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(ADMIN_QUEUE_STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((entry) => entry?.case_id) : [];
  } catch {
    return [];
  }
}

function writeAdminQueueEntries(entries) {
  window.localStorage.setItem(ADMIN_QUEUE_STORAGE_KEY, JSON.stringify(entries));
  window.dispatchEvent(new CustomEvent(ADMIN_QUEUE_UPDATED_EVENT));
}

export function upsertAdminQueueEntry(entry) {
  if (!entry?.case_id) throw new Error("case_id is required for an Admin Queue entry.");
  const entries = getAdminQueueEntries();
  const index = entries.findIndex((item) => item.case_id === entry.case_id);
  if (index === -1) {
    writeAdminQueueEntries([...entries, entry]);
  } else {
    const updated = [...entries];
    updated[index] = { ...updated[index], ...entry };
    writeAdminQueueEntries(updated);
  }
  return entry;
}

export function removeAdminQueueEntry(caseId) {
  const remaining = getAdminQueueEntries().filter((entry) => entry.case_id !== caseId);
  writeAdminQueueEntries(remaining);
}

export function clearAdminQueueEntries() {
  window.localStorage.removeItem(ADMIN_QUEUE_STORAGE_KEY);
  window.dispatchEvent(new CustomEvent(ADMIN_QUEUE_UPDATED_EVENT));
}

export function mergeAdminQueueEntries(serverEntries, localEntries = getAdminQueueEntries()) {
  const byCaseId = new Map();
  for (const entry of serverEntries || []) {
    if (entry?.case_id) byCaseId.set(entry.case_id, entry);
  }
  for (const entry of localEntries || []) {
    if (entry?.case_id) byCaseId.set(entry.case_id, { ...byCaseId.get(entry.case_id), ...entry });
  }
  return [...byCaseId.values()];
}
