import React from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronRight, User, FolderKanban } from "lucide-react";
import { cleanPatientName } from "../../utils/patientNames.js";
import "../../styles/workflow-breadcrumb.css";

/**
 * Resolves breadcrumb items based on current pathname.
 * Returns an array of items: { label: string, to?: string }
 * If the page is a standalone page (not a multi-step workflow), returns null.
 */
export function getBreadcrumbTrail(pathname) {
  const path = (pathname || "/").replace(/\/+$/, "") || "/";

  // =========================================================
  // ADMINISTRATOR MULTI-STEP WORKFLOWS
  // =========================================================
  if (path.startsWith("/admin")) {
    const adminRoot = { label: "Admin Dashboard", to: "/admin/dashboard" };
    const queueStep = { label: "Queue", to: "/admin/queue" };
    const submissionsStep = { label: "Submissions", to: "/admin/submissions" };

    // /admin/queue/:caseId/immediate -> Immediate Review
    const immediateMatch = path.match(/^\/admin\/queue\/([^/]+)\/immediate$/);
    if (immediateMatch) {
      return [adminRoot, queueStep, { label: "Immediate Review" }];
    }

    // /admin/queue/:caseId/individual -> Individual Review
    const individualMatch = path.match(/^\/admin\/queue\/([^/]+)\/individual$/);
    if (individualMatch) {
      return [adminRoot, queueStep, { label: "Individual Review" }];
    }

    // /admin/queue/:caseId -> Case Review
    const queueCaseMatch = path.match(/^\/admin\/queue\/([^/]+)$/);
    if (queueCaseMatch) {
      return [adminRoot, queueStep, { label: "Case Review" }];
    }

    // /admin/batches/:batchId -> Batch Review
    const batchMatch = path.match(/^\/admin\/batches\/([^/]+)$/);
    if (batchMatch) {
      return [adminRoot, queueStep, { label: "Batch Review" }];
    }

    // /admin/submission-journey/:submissionId -> Submission Journey
    if (
      path.startsWith("/admin/submission-journey/") ||
      (path.includes("/submissions/") && path.endsWith("/acknowledgement"))
    ) {
      return [adminRoot, submissionsStep, { label: "Submission Journey" }];
    }

    // Standalone Admin pages (Dashboard, Queue, Deadlines, Submissions, Audit) do not show a workflow bar
    return null;
  }

  // =========================================================
  // CLINICAL STAFF MULTI-STEP WORKFLOWS
  // =========================================================

  const patientsStep = { label: "Patients", to: "/patients" };

  // 1. /patients/:patientId/case/:caseId/reporting-form -> Reporting Form
  const patientFormMatch = path.match(
    /^\/patients\/([^/]+)\/case\/([^/]+)\/reporting-form$/
  );
  if (patientFormMatch) {
    const [, patientId] = patientFormMatch;
    return [
      patientsStep,
      {
        label: "Patient Workspace",
        to: `/patients/${encodeURIComponent(patientId)}`,
      },
      { label: "Reporting Form" },
    ];
  }

  // 2. /patients/:patientId/case/:caseId/completion -> Completion
  const patientCompMatch = path.match(
    /^\/patients\/([^/]+)\/case\/([^/]+)\/completion$/
  );
  if (patientCompMatch) {
    const [, patientId] = patientCompMatch;
    return [
      patientsStep,
      {
        label: "Patient Workspace",
        to: `/patients/${encodeURIComponent(patientId)}`,
      },
      { label: "Completion" },
    ];
  }

  // 3. /patients/:patientId/case/:caseId/queue -> Queue & Follow-up
  const patientQueueMatch = path.match(
    /^\/patients\/([^/]+)\/case\/([^/]+)\/queue$/
  );
  if (patientQueueMatch) {
    const [, patientId] = patientQueueMatch;
    return [
      patientsStep,
      {
        label: "Patient Workspace",
        to: `/patients/${encodeURIComponent(patientId)}`,
      },
      { label: "Queue & Follow-up" },
    ];
  }

  // 4. /patients/:patientId/case/:caseId/submission -> Review & Validation
  const patientSubMatch = path.match(
    /^\/patients\/([^/]+)\/case\/([^/]+)\/submission$/
  );
  if (patientSubMatch) {
    const [, patientId] = patientSubMatch;
    return [
      patientsStep,
      {
        label: "Patient Workspace",
        to: `/patients/${encodeURIComponent(patientId)}`,
      },
      { label: "Review & Validation" },
    ];
  }

  // 5. /patients/:patientId/case/:caseId -> Case Review
  const patientCaseMatch = path.match(/^\/patients\/([^/]+)\/case\/([^/]+)$/);
  if (patientCaseMatch) {
    const [, patientId] = patientCaseMatch;
    return [
      patientsStep,
      {
        label: "Patient Workspace",
        to: `/patients/${encodeURIComponent(patientId)}`,
      },
      { label: "Case Review" },
    ];
  }

  // 6. /patients/:patientId -> Patient Workspace
  const patientDetailMatch = path.match(/^\/patients\/([^/]+)$/);
  if (patientDetailMatch) {
    return [patientsStep, { label: "Patient Workspace" }];
  }

  // 7. /submissions/case/:caseId -> Submission Workspace
  const subCaseMatch = path.match(/^\/submissions\/case\/([^/]+)$/);
  if (subCaseMatch) {
    return [
      { label: "Submissions", to: "/submissions" },
      { label: "Submission Workspace" },
    ];
  }

  // 8. /cases/:caseId nested paths
  const casesStep = { label: "Cases", to: "/cases" };

  const caseFormMatch = path.match(/^\/cases\/([^/]+)\/reporting-form$/);
  if (caseFormMatch) {
    const [, caseId] = caseFormMatch;
    return [
      casesStep,
      {
        label: "Case Workspace",
        to: `/cases/${encodeURIComponent(caseId)}`,
      },
      { label: "Reporting Form" },
    ];
  }

  const caseCompMatch = path.match(/^\/cases\/([^/]+)\/completion$/);
  if (caseCompMatch) {
    const [, caseId] = caseCompMatch;
    return [
      casesStep,
      {
        label: "Case Workspace",
        to: `/cases/${encodeURIComponent(caseId)}`,
      },
      { label: "Completion" },
    ];
  }

  const caseQueueMatch = path.match(/^\/cases\/([^/]+)\/queue$/);
  if (caseQueueMatch) {
    const [, caseId] = caseQueueMatch;
    return [
      casesStep,
      {
        label: "Case Workspace",
        to: `/cases/${encodeURIComponent(caseId)}`,
      },
      { label: "Queue & Follow-up" },
    ];
  }

  const caseDetailMatch = path.match(/^\/cases\/([^/]+)$/);
  if (caseDetailMatch) {
    return [casesStep, { label: "Case Workspace" }];
  }

  // Standalone pages (Patients, Dashboard, Cases, Submissions, Analytics, Audit, Governance) do not show a workflow bar
  return null;
}

/**
 * Extracts supplementary context from location state or router params.
 */
function getSupplementaryContext(location) {
  const state = location.state || {};
  if (state.patientName) return { type: "patient", label: cleanPatientName(state.patientName) };
  if (state.caseData?.patientName) return { type: "patient", label: cleanPatientName(state.caseData.patientName) };
  if (state.patient?.name) return { type: "patient", label: cleanPatientName(state.patient.name) };
  if (state.patient?.full_name) return { type: "patient", label: cleanPatientName(state.patient.full_name) };
  if (state.condition) return { type: "condition", label: state.condition };
  if (state.caseData?.condition) return { type: "condition", label: state.caseData.condition };
  if (state.caseData?.disease) return { type: "condition", label: state.caseData.disease };
  return null;
}

export function WorkflowBreadcrumb({ admin = false }) {
  const location = useLocation();
  const trail = getBreadcrumbTrail(location.pathname);
  const context = getSupplementaryContext(location);

  // Do not render breadcrumbs on standalone pages or single-level views
  if (!trail || trail.length <= 1) {
    return null;
  }

  return (
    <nav
      className={`workflow-breadcrumb-bar${admin ? " admin-breadcrumb-bar" : ""}`}
      aria-label="Workflow Navigation"
    >
      <ol className="workflow-breadcrumb-trail">
        {trail.map((item, index) => {
          const isCurrent = index === trail.length - 1;

          return (
            <li key={`${item.label}-${index}`} className="workflow-breadcrumb-step">
              {index > 0 && (
                <span className="workflow-breadcrumb-separator" aria-hidden="true">
                  <ChevronRight size={13} />
                </span>
              )}

              {isCurrent || !item.to ? (
                <span
                  className="workflow-breadcrumb-current"
                  aria-current={isCurrent ? "page" : undefined}
                >
                  {item.label}
                </span>
              ) : (
                <Link to={item.to} className="workflow-breadcrumb-link">
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>

      {context && (
        <div className="workflow-breadcrumb-context" aria-label="Current workflow context">
          <span className="workflow-breadcrumb-chip">
            {context.type === "patient" && <User size={12} aria-hidden="true" />}
            {context.type === "condition" && <FolderKanban size={12} aria-hidden="true" />}
            <span>{context.label}</span>
          </span>
        </div>
      )}
    </nav>
  );
}

export default WorkflowBreadcrumb;
