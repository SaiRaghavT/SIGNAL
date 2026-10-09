import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell.jsx";
import AdminShell from "./components/layout/AdminShell.jsx";
import { SignalLoading } from "./components/ui/SignalLoading.jsx";
import { SignalAssistant } from "./components/ui/SignalAssistant.jsx";

const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Patients = lazy(() => import("./pages/Patients.jsx"));
const PatientWorkspace = lazy(() => import("./pages/PatientWorkspace.jsx"));
const CasesPage = lazy(() => import("./pages/CasesPage.jsx").then((module) => ({ default: module.CasesPage })));
const CaseWorkspacePage = lazy(() => import("./pages/CaseWorkspacePage.jsx"));
const SubmissionsPage = lazy(() => import("./pages/SubmissionsPage.jsx").then((module) => ({ default: module.SubmissionsPage })));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage.jsx").then((module) => ({ default: module.AnalyticsPage })));
const AuditPage = lazy(() => import("./pages/AuditPage.jsx").then((module) => ({ default: module.AuditPage })));
const AdminDashboard = lazy(() => import("./pages/admin/AdminDashboard.jsx"));
const AdminAudit = lazy(() => import("./pages/admin/AdminAudit.jsx"));
const AdminDeadlines = lazy(() => import("./pages/admin/AdminDeadlines.jsx"));
const AdminImmediateReview = lazy(() => import("./pages/admin/AdminImmediateReview.jsx"));
const AdminIndividualReview = lazy(() => import("./pages/admin/AdminIndividualReview.jsx"));
const AdminBatchReview = lazy(() => import("./pages/admin/AdminBatchReview.jsx"));
const AdminQueue = lazy(() => import("./pages/admin/AdminQueue.jsx"));
const Login = lazy(() => import("./pages/Login.jsx"));
const AdminSubmissions = lazy(() => import("./pages/admin/AdminSubmissions.jsx"));
const AdminSubmissionAcknowledgement = lazy(() => import("./pages/admin/AdminSubmissionAcknowledgement.jsx"));
const AdminSubmissionJourney = lazy(() => import("./pages/admin/AdminSubmissionJourney.jsx"));
const ReportingFormPage = lazy(() => import("./pages/ReportingFormPage.jsx"));
const SubmissionWorkspace = lazy(() => import("./pages/SubmissionWorkspace.jsx"));
const CaseCompletion = lazy(() => import("./pages/CaseCompletion.jsx"));
const QueueAcknowledgementPage = lazy(() => import("./pages/QueueAcknowledgementPage.jsx"));
const AdminCaseReview = lazy(() => import("./pages/admin/AdminCaseReview.jsx"));
const FollowUpWorkspace = lazy(() => import("./pages/FollowUpWorkspace.jsx"));
const FollowupsPage = lazy(() => import("./pages/FollowupsPage.jsx").then((module) => ({ default: module.FollowupsPage })));
const loadReportingAdminPages = () => import("./pages/ReportingAdmin.jsx");
const ReportingAdminQueue = lazy(() => loadReportingAdminPages().then((module) => ({ default: module.ReportingAdminQueue })));
const ReportingAdminCaseReview = lazy(() => loadReportingAdminPages().then((module) => ({ default: module.ReportingAdminCaseReview })));
const ReportingAdminSubmissionDetail = lazy(() => loadReportingAdminPages().then((module) => ({ default: module.ReportingAdminSubmissionDetail })));
const ReportingAdminSettings = lazy(() => loadReportingAdminPages().then((module) => ({ default: module.ReportingAdminSettings })));
const loadGovernancePages = () => import("./pages/AiGovernance.jsx");
const GovernanceOverview = lazy(() => loadGovernancePages().then((module) => ({ default: module.GovernanceOverview })));
const MonitoringPage = lazy(() => loadGovernancePages().then((module) => ({ default: module.MonitoringPage })));
const EvaluationPage = lazy(() => loadGovernancePages().then((module) => ({ default: module.EvaluationPage })));
const ExplainabilityPage = lazy(() => loadGovernancePages().then((module) => ({ default: module.ExplainabilityPage })));
const AgentGovernancePage = lazy(() => loadGovernancePages().then((module) => ({ default: module.AgentGovernancePage })));
const AgentDetailPage = lazy(() => loadGovernancePages().then((module) => ({ default: module.AgentDetailPage })));
const OutcomeLearningPage = lazy(() => loadGovernancePages().then((module) => ({ default: module.OutcomeLearningPage })));
const LearningSignalDetail = lazy(() => loadGovernancePages().then((module) => ({ default: module.LearningSignalDetail })));

// Clear temporary workflow values whenever the frontend boots.
if (typeof window !== "undefined") {
  const transientPrefixes = [
    "signal:missing-information:",
    "signal:reporting-preview:",
    "signal:case-workflow-session:",
    "signal:demo-workflow:",
  ];
  for (const storage of [window.sessionStorage, window.localStorage]) {
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (key && transientPrefixes.some((prefix) => key.startsWith(prefix))) {
        storage.removeItem(key);
      }
    }
  }
}

export default function App() {
  return (
    <Suspense fallback={<SignalLoading title="Loading SIGNAL" message="Preparing your workspace." />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/:patientId" element={<PatientWorkspace />} />
          <Route path="/patients/:patientId/case/:caseId" element={<CaseWorkspacePage />} />
          <Route path="/patients/:patientId/case/:caseId/reporting-form" element={<ReportingFormPage />} />
          <Route path="/patients/:patientId/case/:caseId/submission" element={<SubmissionWorkspace />} />
          <Route path="/patients/:patientId/case/:caseId/follow-up" element={<FollowUpWorkspace />} />
          <Route path="/patients/:patientId/case/:caseId/completion" element={<CaseCompletion />} />
          <Route path="/patients/:patientId/case/:caseId/queue" element={<QueueAcknowledgementPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/:caseId" element={<CaseWorkspacePage />} />
          <Route path="/cases/:caseId/reporting-form" element={<ReportingFormPage />} />
          <Route path="/cases/:caseId/completion" element={<CaseCompletion />} />
          <Route path="/cases/:caseId/queue" element={<QueueAcknowledgementPage />} />
          <Route path="/follow-ups" element={<FollowupsPage />} />
          <Route path="/follow-ups/case/:caseId" element={<FollowUpWorkspace />} />
          <Route path="/submissions" element={<SubmissionsPage />} />
          <Route path="/submissions/case/:caseId" element={<SubmissionWorkspace />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/governance" element={<GovernanceOverview />} />
          <Route path="/governance/monitoring" element={<MonitoringPage />} />
          <Route path="/governance/evaluation" element={<EvaluationPage />} />
          <Route path="/governance/explainability" element={<ExplainabilityPage />} />
          <Route path="/governance/agents" element={<AgentGovernancePage />} />
          <Route path="/governance/agents/:agentId" element={<AgentDetailPage />} />
          <Route path="/governance/outcome-learning" element={<OutcomeLearningPage />} />
          <Route path="/governance/outcome-learning/:signalId" element={<LearningSignalDetail />} />
        </Route>
        <Route element={<AdminShell />}>
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
          <Route path="/admin/queue" element={<AdminQueue />} />
          <Route path="/admin/deadlines" element={<AdminDeadlines />} />
          <Route path="/admin/follow-ups" element={<FollowupsPage />} />
          <Route path="/admin/reporting-queue" element={<ReportingAdminQueue />} />
          <Route path="/admin/reporting-queue/batch" element={<Navigate to="/admin/queue" replace />} />
          <Route path="/admin/reporting-queue/:id" element={<ReportingAdminCaseReview />} />
          <Route path="/admin/submission-batches" element={<Navigate to="/admin/queue" replace />} />
          <Route path="/admin/submission-batches/:batchId" element={<AdminBatchReview />} />
          <Route path="/admin/settings" element={<ReportingAdminSettings />} />
          <Route path="/admin/audit" element={<AdminAudit />} />
          <Route path="/admin/batches/:batchId" element={<AdminBatchReview />} />
          <Route path="/admin/queue/:caseId/immediate" element={<AdminImmediateReview />} />
          <Route path="/admin/queue/:caseId/individual" element={<AdminIndividualReview />} />
          <Route path="/admin/queue/:caseId" element={<AdminCaseReview />} />
          <Route path="/admin/submissions" element={<AdminSubmissions />} />
          <Route path="/admin/submissions/:batchId" element={<ReportingAdminSubmissionDetail />} />
          <Route path="/admin/submissions/:submissionId/acknowledgement" element={<AdminSubmissionAcknowledgement />} />
          <Route path="/admin/submission-journey/:submissionId" element={<AdminSubmissionJourney />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
      <SignalAssistant />
    </Suspense>
  );
}
