import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Clock3,
  Layers3,
  RefreshCw,
  Zap,
} from "lucide-react";
import {
  getAdminBatches,
  getAdminQueue,
} from "../../services/adminService";
import {
  ADMIN_QUEUE_UPDATED_EVENT,
} from "../../utils/adminQueueLocalStorage.js";
import "../../styles/AdminQueue.css";

const MODES = {
  IMMEDIATE: "IMMEDIATE",
  INDIVIDUAL: "INDIVIDUAL",
  BATCH: "BATCH",
};

const EMPTY_QUEUE = {
  items: [],
  total: 0,
};

const EMPTY_BATCHES = {
  items: [],
  total: 0,
};

const DEMO_PATIENT_NAMES = [
  "Avery Parker (Demo)",
  "Morgan Ellis (Demo)",
  "Riley Bennett (Demo)",
  "Jamie Foster (Demo)",
  "Cameron Hayes (Demo)",
];

function demoIndex(caseId) {
  return Array.from(String(caseId || "")).reduce(
    (total, character) => total + character.charCodeAt(0),
    0,
  );
}

function getDisplayPatientName(item) {
  const name = getPatientName(item);
  if (name !== "—" && name !== "â€”") return name;
  const caseId = getCaseId(item);
  return caseId ? DEMO_PATIENT_NAMES[demoIndex(caseId) % DEMO_PATIENT_NAMES.length] : name;
}

function getDisplayDeadline(item) {
  const deadline = getDeadline(item);
  if (deadline !== "—" && deadline !== "â€”") return deadline;

  const caseId = getCaseId(item);
  if (!caseId) return deadline;

  const offsetDays = (demoIndex(caseId) % 5) + 1;
  const fallback = new Date();
  fallback.setDate(fallback.getDate() + offsetDays);
  fallback.setHours(17 + (demoIndex(caseId) % 5), 0, 0, 0);
  return `${fallback.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} (Demo)`;
}

function getDisplayPriority(item) {
  const priority = getPriority(item);
  if (priority !== "—" && priority !== "â€”") return priority;

  const caseId = getCaseId(item);
  if (!caseId) return priority;

  const demoPriorities = ["HIGH", "MEDIUM", "URGENT", "LOW"];
  return `${demoPriorities[demoIndex(caseId) % demoPriorities.length]} (Demo)`;
}

function getResponseItems(response) {
  if (Array.isArray(response)) {
    return response;
  }

  if (Array.isArray(response?.items)) {
    return response.items;
  }

  if (Array.isArray(response?.records)) {
    return response.records;
  }

  if (Array.isArray(response?.data)) {
    return response.data;
  }

  return [];
}

function getResponseTotal(response, items) {
  if (typeof response?.total === "number") {
    return response.total;
  }

  if (typeof response?.count === "number") {
    return response.count;
  }

  return items.length;
}

function normalizeMode(item) {
  return String(
    item?.submission_mode ||
      item?.submissionMode ||
      item?.mode ||
      ""
  ).toUpperCase();
}

function getStatusClass(status) {
  const value = String(status || "").toUpperCase();

  if (
    value.includes("READY") ||
    value.includes("PENDING") ||
    value.includes("QUEUED")
  ) {
    return "status-warning";
  }

  if (
    value.includes("SUBMITTED") ||
    value.includes("ACKNOWLEDGED") ||
    value.includes("SUCCESS")
  ) {
    return "status-success";
  }

  if (
    value.includes("FAILED") ||
    value.includes("ERROR") ||
    value.includes("RETRY")
  ) {
    return "status-danger";
  }

  return "status-neutral";
}

function getPriorityClass(priority) {
  const value = String(priority || "").toUpperCase();

  if (
    value.includes("URGENT") ||
    value.includes("CRITICAL")
  ) {
    return "priority-urgent";
  }

  if (value.includes("HIGH")) {
    return "priority-high";
  }

  if (value.includes("MEDIUM")) {
    return "priority-medium";
  }

  return "priority-normal";
}

function formatValue(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  return String(value);
}

function formatModeLabel(mode) {
  if (mode === MODES.IMMEDIATE) {
    return "Immediate";
  }

  if (mode === MODES.INDIVIDUAL) {
    return "Individual";
  }

  if (mode === MODES.BATCH) {
    return "Batch";
  }

  return formatValue(mode);
}

function getPatientName(item) {
  return (
    item?.patient_name ||
    item?.patientName ||
    item?.patient?.name ||
    item?.patient?.full_name ||
    "—"
  );
}

function getCondition(item) {
  return (
    item?.condition ||
    item?.disease ||
    item?.disease_name ||
    item?.diseaseName ||
    "—"
  );
}

function getCaseId(item) {
  return (
    item?.case_id ||
    item?.caseId ||
    item?.id ||
    ""
  );
}

function getJurisdiction(item) {
  return (
    item?.jurisdiction_name ||
    item?.jurisdictionName ||
    item?.jurisdiction ||
    "—"
  );
}

function getDeadline(item) {
  return (
    item?.deadline ||
    item?.due_at ||
    item?.dueAt ||
    item?.reporting_deadline ||
    "—"
  );
}

function getPriority(item) {
  return (
    item?.priority ||
    item?.severity ||
    "—"
  );
}

function getStatus(item) {
  return (
    item?.status ||
    item?.queue_status ||
    item?.queueStatus ||
    "—"
  );
}

function getBatchId(item) {
  return (
    item?.batch_id ||
    item?.batchId ||
    item?.id ||
    ""
  );
}

function getBatchDestination(item) {
  return (
    item?.destination ||
    item?.destination_name ||
    item?.destinationName ||
    "—"
  );
}

function getBatchCondition(item) {
  return (
    item?.condition ||
    item?.disease ||
    item?.disease_name ||
    item?.diseaseName ||
    "—"
  );
}

function getBatchCaseCount(item) {
  if (typeof item?.case_count === "number") {
    return item.case_count;
  }

  if (typeof item?.caseCount === "number") {
    return item.caseCount;
  }

  if (Array.isArray(item?.case_ids)) {
    return item.case_ids.length;
  }

  if (Array.isArray(item?.caseIds)) {
    return item.caseIds.length;
  }

  if (Array.isArray(item?.cases)) {
    return item.cases.length;
  }

  return "—";
}

function getBatchWindow(item) {
  return (
    item?.reporting_window ||
    item?.reportingWindow ||
    item?.window ||
    item?.date_range ||
    item?.dateRange ||
    "—"
  );
}

export default function AdminQueue() {
  const navigate = useNavigate();

  const [queue, setQueue] = useState(EMPTY_QUEUE);
  const [batches, setBatches] = useState(
    EMPTY_BATCHES
  );

  const [activeMode, setActiveMode] = useState(
    MODES.IMMEDIATE
  );

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadData = useCallback(
    async (isRefresh = false) => {
      try {
        setError("");

        if (isRefresh) {
          setRefreshing(true);
        } else {
          setLoading(true);
        }

        const [queueResponse, batchResponse] =
          await Promise.all([
            getAdminQueue(),
            getAdminBatches(),
          ]);

        const queueItems =
          getResponseItems(queueResponse);

        const batchItems =
          getResponseItems(batchResponse);

        setQueue({
          items: queueItems,
          total: queueItems.length,
        });

        setBatches({
          items: batchItems,
          total: getResponseTotal(
            batchResponse,
            batchItems
          ),
        });
      } catch (requestError) {
        console.error(
          "Failed to load admin reporting queue:",
          requestError
        );

        setError(
          requestError?.message ||
            "Unable to load the reporting queue."
        );
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    []
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const refreshQueue = () => loadData(true);
    window.addEventListener(ADMIN_QUEUE_UPDATED_EVENT, refreshQueue);
    return () => {
      window.removeEventListener(ADMIN_QUEUE_UPDATED_EVENT, refreshQueue);
    };
  }, [loadData]);

  const modeCounts = useMemo(() => {
    const immediate = queue.items.filter(
      (item) =>
        normalizeMode(item) === MODES.IMMEDIATE
    ).length;

    const individual = queue.items.filter(
      (item) =>
        normalizeMode(item) === MODES.INDIVIDUAL
    ).length;

    return {
      immediate,
      individual,
      batch: batches.items.length,
    };
  }, [queue.items, batches.items]);

  const visibleCases = useMemo(() => {
    return queue.items.filter(
      (item) => normalizeMode(item) === activeMode
    );
  }, [queue.items, activeMode]);

  const openCaseReview = (caseId, submissionMode) => {
    if (!caseId) {
      return;
    }

    const reviewPath = submissionMode === MODES.INDIVIDUAL
      ? "individual"
      : "immediate";
    navigate(`/admin/queue/${caseId}/${reviewPath}`);
  };

  const openBatchReview = (batchId) => {
    if (!batchId) {
      return;
    }

    navigate(`/admin/batches/${batchId}`);
  };

  return (
    <main className="admin-queue-page">
      <header className="admin-page-header">
        <div>
          <div className="admin-page-kicker">
            REPORTING OPERATIONS
          </div>

          <h1>Reporting Queue</h1>

          <p>
            Review, validate and authorize reporting
            packages prepared by SIGNAL.
          </p>
        </div>

        <button
          type="button"
          className="admin-refresh-button"
          onClick={() => loadData(true)}
          disabled={loading || refreshing}
        >
          <RefreshCw
            size={16}
            className={
              refreshing ? "spinning" : ""
            }
          />

          {refreshing
            ? "Refreshing..."
            : "Refresh"}
        </button>
      </header>

      {error && (
        <section className="admin-error-state">
          <AlertCircle size={18} />

          <div>
            <strong>
              Unable to load reporting queue
            </strong>

            <p>{error}</p>
          </div>

          <button
            type="button"
            onClick={() => loadData()}
          >
            Retry
          </button>
        </section>
      )}

      <section className="admin-queue-mode-cards">
        <button
          type="button"
          className={`admin-mode-card ${
            activeMode === MODES.IMMEDIATE
              ? "active"
              : ""
          }`}
          onClick={() =>
            setActiveMode(MODES.IMMEDIATE)
          }
        >
          <div className="admin-mode-icon immediate">
            <Zap size={19} />
          </div>

          <div className="admin-mode-content">
            <span>IMMEDIATE</span>

            <strong>
              {modeCounts.immediate}
            </strong>

            <p>
              Urgent reports requiring
              immediate authorization
            </p>
          </div>
        </button>

        <button
          type="button"
          className={`admin-mode-card ${
            activeMode === MODES.INDIVIDUAL
              ? "active"
              : ""
          }`}
          onClick={() =>
            setActiveMode(MODES.INDIVIDUAL)
          }
        >
          <div className="admin-mode-icon individual">
            <Clock3 size={19} />
          </div>

          <div className="admin-mode-content">
            <span>INDIVIDUAL</span>

            <strong>
              {modeCounts.individual}
            </strong>

            <p>
              One patient per
              submission
            </p>
          </div>
        </button>

        <button
          type="button"
          className={`admin-mode-card ${
            activeMode === MODES.BATCH
              ? "active"
              : ""
          }`}
          onClick={() =>
            setActiveMode(MODES.BATCH)
          }
        >
          <div className="admin-mode-icon batch">
            <Layers3 size={19} />
          </div>

          <div className="admin-mode-content">
            <span>BATCH</span>

            <strong>
              {modeCounts.batch}
            </strong>

            <p>
              Backend-generated
              reporting batches
            </p>
          </div>
        </button>
      </section>

      <section className="admin-queue-card">
        <div className="admin-section-header">
          <div>
            <span className="admin-section-kicker">
              {activeMode === MODES.BATCH
                ? "BACKEND-GENERATED BATCHES"
                : "REPORTING WORK"}
            </span>

            <h2>
              {activeMode === MODES.IMMEDIATE &&
                "Immediate Reporting"}

              {activeMode === MODES.INDIVIDUAL &&
                "Individual Reporting"}

              {activeMode === MODES.BATCH &&
                "Backend-Generated Batches"}
            </h2>

            <p className="admin-section-description">
              {activeMode === MODES.IMMEDIATE &&
                "Cases requiring immediate administrative authorization."}

              {activeMode === MODES.INDIVIDUAL &&
                "Cases prepared for one-patient-per-submission reporting."}

              {activeMode === MODES.BATCH &&
                "Batches generated by SIGNAL for administrative review and authorization."}
            </p>
          </div>

          <span className="admin-record-count">
            {activeMode === MODES.BATCH
              ? `${batches.total} batch${
                  batches.total === 1
                    ? ""
                    : "es"
                }`
              : `${visibleCases.length} case${
                  visibleCases.length === 1
                    ? ""
                    : "s"
                }`}
          </span>
        </div>

        {loading ? (
          <div className="admin-loading-state">
            <RefreshCw
              size={20}
              className="spinning"
            />

            <span>
              Loading reporting operations...
            </span>
          </div>
        ) : activeMode === MODES.BATCH ? (
          batches.items.length === 0 ? (
            <div className="admin-empty-state">
              <Layers3 size={28} />

              <h3>
                No reporting batches available
              </h3>

              <p>
                Backend-generated reporting
                batches will appear here when
                eligible cases are grouped for
                dispatch.
              </p>
            </div>
          ) : (
            <div className="admin-table-wrapper">
              <table className="admin-queue-table">
                <thead>
                  <tr>
                    <th>Batch ID</th>
                    <th>Destination</th>
                    <th>Condition</th>
                    <th>Cases</th>
                    <th>Reporting Window</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>

                <tbody>
                  {batches.items.map(
                    (batch, index) => {
                      const batchId =
                        getBatchId(batch);

                      const status =
                        batch?.status ||
                        batch?.batch_status ||
                        batch?.batchStatus ||
                        "—";

                      return (
                        <tr
                          key={
                            batchId
                              ? `batch-${batchId}`
                              : `batch-row-${index}`
                          }
                        >
                          <td>
                            <span className="case-id">
                              {formatValue(
                                batch?.display_batch_id || batchId
                              )}
                            </span>
                            {batch?.display_batch_id && batch?.display_batch_id !== batchId && (
                              <small className="batch-record-id">Record: {formatValue(batchId)}</small>
                            )}
                          </td>

                          <td>
                            {formatValue(
                              getBatchDestination(
                                batch
                              )
                            )}
                          </td>

                          <td>
                            {formatValue(
                              getBatchCondition(
                                batch
                              )
                            )}
                          </td>

                          <td>
                            <span className="batch-case-count">
                              {getBatchCaseCount(
                                batch
                              )}
                            </span>
                          </td>

                          <td>
                            {formatValue(
                              getBatchWindow(
                                batch
                              )
                            )}
                          </td>

                          <td>
                            <span
                              className={`status-pill ${getStatusClass(
                                status
                              )}`}
                            >
                              {formatValue(
                                status
                              )}
                            </span>
                          </td>

                          <td>
                            {batchId ? (
                              <button
                                type="button"
                                className="admin-review-link"
                                onClick={() =>
                                  openBatchReview(
                                    batchId
                                  )
                                }
                              >
                                Review Batch
                                <ArrowRight
                                  size={15}
                                />
                              </button>
                            ) : (
                              <span className="unavailable-action">
                                —
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    }
                  )}
                </tbody>
              </table>
            </div>
          )
        ) : visibleCases.length === 0 ? (
          <div className="admin-empty-state">
            {activeMode === MODES.IMMEDIATE ? (
              <Zap size={28} />
            ) : (
              <Clock3 size={28} />
            )}

            <h3>
              No{" "}
              {activeMode === MODES.IMMEDIATE
                ? "immediate"
                : "individual"}{" "}
              reports in the queue
            </h3>

            <p>
              Reporting cases classified for this
              pathway will appear here after
              Clinical Staff submits them to the
              administrative queue.
            </p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-queue-table">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Case ID</th>
                  <th>Condition</th>
                  <th>Jurisdiction</th>
                  <th>Deadline</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {visibleCases.map(
                  (item, index) => {
                    const caseId =
                      getCaseId(item);

                    const priority =
                      getDisplayPriority(item);

                    const status =
                      getStatus(item);

                    return (
                      <tr
                        key={
                          caseId
                            ? `case-${caseId}`
                            : `case-row-${index}`
                        }
                      >
                        <td>
                          <span className="patient-name">
                            {formatValue(getDisplayPatientName(item))}
                          </span>
                        </td>

                        <td>
                          <span className="case-id">
                            {formatValue(
                              caseId
                            )}
                          </span>
                        </td>

                        <td>
                          {formatValue(
                            getCondition(item)
                          )}
                        </td>

                        <td>
                          {formatValue(
                            getJurisdiction(
                              item
                            )
                          )}
                        </td>

                        <td>
                          <span className="deadline-value">
                            {formatValue(getDisplayDeadline(item))}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`priority-pill ${getPriorityClass(
                              priority
                            )}`}
                          >
                            {formatValue(
                              priority
                            )}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`status-pill ${getStatusClass(
                              status
                            )}`}
                          >
                            {formatValue(
                              status
                            )}
                          </span>
                        </td>

                        <td>
                          {caseId ? (
                            <button
                              type="button"
                              className="admin-review-link"
                              onClick={() =>
                                openCaseReview(
                                  caseId,
                                  normalizeMode(item)
                                )
                              }
                            >
                              Review &amp;
                              Authorize
                              <ArrowRight
                                size={15}
                              />
                            </button>
                          ) : (
                            <span className="unavailable-action">
                              —
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  }
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
