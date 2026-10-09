
import { Navigate, Route, Routes, useParams } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell.jsx";
import AdminShell from "./components/layout/AdminShell.jsx";
import Login from "./pages/Login.jsx";

// Clinical pages
import Dashboard from "./pages/Dashboard.jsx";
import Patients from "./pages/Patients.jsx";
import PatientWorkspace from "./pages/PatientWorkspace.jsx";
import { CasesPage } from "./pages/CasesPage.jsx";
import CaseWorkspacePage from "./pages/CaseWorkspacePage.jsx";
import ReportingFormPage from "./pages/ReportingFormPage.jsx";
import SubmissionWorkspace from "./pages/SubmissionWorkspace.jsx";
import CaseCompletion from "./pages/CaseCompletion.jsx";
import QueueAcknowledgementPage from "./pages/QueueAcknowledgementPage.jsx";
import { SubmissionsPage } from "./pages/SubmissionsPage.jsx";
import { AnalyticsPage } from "./pages/AnalyticsPage.jsx";
import { AuditPage } from "./pages/AuditPage.jsx";

// Admin pages
import AdminDashboard from "./pages/admin/AdminDashboard.jsx";
import AdminAudit from "./pages/admin/AdminAudit.jsx";
import AdminDeadlines from "./pages/admin/AdminDeadlines.jsx";
import AdminImmediateReview from "./pages/admin/AdminImmediateReview.jsx";
import AdminIndividualReview from "./pages/admin/AdminIndividualReview.jsx";
import AdminBatchReview from "./pages/admin/AdminBatchReview.jsx";
import AdminQueue from "./pages/admin/AdminQueue.jsx";
import AdminSubmissions from "./pages/admin/AdminSubmissions.jsx";
import AdminSubmissionJourney from "./pages/admin/AdminSubmissionJourney.jsx";
import AdminCaseReview from "./pages/admin/AdminCaseReview.jsx";

// AI Governance
import {
  AgentDetailPage,
  AgentGovernancePage,
  EvaluationPage,
  ExplainabilityPage,
  GovernanceOverview,
  LearningSignalDetail,
  MonitoringPage,
  OutcomeLearningPage,
} from "./pages/AiGovernance.jsx";

import "./styles/ai-governance-feature.css";
import "./styles/AiGovernance.css";

function getStoredUser() {
  try {
    const sessionUser = sessionStorage.getItem("signal-user");
    const localUser = localStorage.getItem("signal-user");

    const raw = sessionUser || localUser;
    if (!raw) return null;

    const user = JSON.parse(raw);

    if (
      user?.role !== "Administrator" &&
      user?.role !== "Clinical Staff"
    ) {
      return null;
    }

    return user;
  } catch {
    return null;
  }
}

function isAuthenticated() {
  return (
    sessionStorage.getItem("signal-auth") === "true" ||
    localStorage.getItem("signal-auth") === "true"
  );
}

function getRoleHome(role) {
  return role === "Administrator" ? "/admin/dashboard" : "/dashboard";
}

function RequireRole({ allowedRoles, children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  const user = getStoredUser();

  if (!user) {
    sessionStorage.removeItem("signal-auth");
    sessionStorage.removeItem("signal-user");
    localStorage.removeItem("signal-auth");
    localStorage.removeItem("signal-user");
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to={getRoleHome(user.role)} replace />;
  }

  return children;
}

function RoleHome() {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  const user = getStoredUser();

  if (!user?.role) {
    sessionStorage.removeItem("signal-auth");
    sessionStorage.removeItem("signal-user");
    localStorage.removeItem("signal-auth");
    localStorage.removeItem("signal-user");

    return <Navigate to="/login" replace />;
  }

  return <Navigate to={getRoleHome(user.role)} replace />;
}

function LegacySubmissionAcknowledgementRoute() {
  const { submissionId } = useParams();

  return (
    <Navigate
      replace
      to={`/admin/submission-journey/${encodeURIComponent(submissionId)}`}
    />
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      {/* Clinical Staff application */}
      <Route
        element={
          <RequireRole allowedRoles={["Clinical Staff"]}>
            <AppShell />
          </RequireRole>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />

        <Route path="/patients" element={<Patients />} />
        <Route path="/patients/:patientId" element={<PatientWorkspace />} />

        <Route
          path="/patients/:patientId/case/:caseId"
          element={<CaseWorkspacePage />}
        />
        <Route
          path="/patients/:patientId/case/:caseId/reporting-form"
          element={<ReportingFormPage />}
        />
        <Route
          path="/patients/:patientId/case/:caseId/submission"
          element={<SubmissionWorkspace />}
        />
        <Route
          path="/patients/:patientId/case/:caseId/completion"
          element={<CaseCompletion />}
        />
        <Route
          path="/patients/:patientId/case/:caseId/queue"
          element={<QueueAcknowledgementPage />}
        />

        <Route path="/cases" element={<CasesPage />} />
        <Route path="/cases/:caseId" element={<CaseWorkspacePage />} />
        <Route
          path="/cases/:caseId/reporting-form"
          element={<ReportingFormPage />}
        />
        <Route
          path="/cases/:caseId/completion"
          element={<CaseCompletion />}
        />
        <Route
          path="/cases/:caseId/queue"
          element={<QueueAcknowledgementPage />}
        />

        <Route path="/submissions" element={<SubmissionsPage />} />
        <Route
          path="/submissions/case/:caseId"
          element={<SubmissionWorkspace />}
        />

        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/audit" element={<AuditPage />} />

        {/* AI Governance */}
        <Route path="/governance" element={<GovernanceOverview />} />
        <Route path="/governance/monitoring" element={<MonitoringPage />} />
        <Route path="/governance/evaluation" element={<EvaluationPage />} />
        <Route
          path="/governance/explainability"
          element={<ExplainabilityPage />}
        />
        <Route
          path="/governance/agents"
          element={<AgentGovernancePage />}
        />
        <Route
          path="/governance/agents/:agentId"
          element={<AgentDetailPage />}
        />
        <Route
          path="/governance/outcome-learning"
          element={<OutcomeLearningPage />}
        />
        <Route
          path="/governance/outcome-learning/:signalId"
          element={<LearningSignalDetail />}
        />
      </Route>

      {/* Administrator application */}
      <Route
        path="/admin"
        element={
          <RequireRole allowedRoles={["Administrator"]}>
            <AdminShell />
          </RequireRole>
        }
      >
        <Route
          index
          element={<Navigate to="/admin/dashboard" replace />}
        />

        <Route path="dashboard" element={<AdminDashboard />} />
        <Route path="queue" element={<AdminQueue />} />

        <Route
          path="queue/:caseId/immediate"
          element={<AdminImmediateReview />}
        />
        <Route
          path="queue/:caseId/individual"
          element={<AdminIndividualReview />}
        />
        <Route
          path="queue/:caseId"
          element={<AdminCaseReview />}
        />

        <Route path="batches/:batchId" element={<AdminBatchReview />} />
        <Route path="deadlines" element={<AdminDeadlines />} />
        <Route path="audit" element={<AdminAudit />} />
        <Route path="submissions" element={<AdminSubmissions />} />

        <Route
          path="submission-journey/:submissionId"
          element={<AdminSubmissionJourney />}
        />

        <Route
          path="submissions/:submissionId/acknowledgement"
          element={<LegacySubmissionAcknowledgementRoute />}
        />
      </Route>

      {/* Role-aware homepage and fallback */}
      <Route path="/" element={<RoleHome />} />
      <Route path="*" element={<RoleHome />} />
    </Routes>
  );
}
