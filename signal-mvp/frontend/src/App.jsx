import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Patients from "./pages/Patients.jsx";
import PatientWorkspace from "./pages/PatientWorkspace.jsx";
import { CasesPage } from "./pages/CasesPage.jsx";
import CaseWorkspacePage from "./pages/CaseWorkspacePage.jsx";
import { SubmissionsPage } from "./pages/SubmissionsPage.jsx";
import { AnalyticsPage } from "./pages/AnalyticsPage.jsx";
import { AuditPage } from "./pages/AuditPage.jsx";
import Login from "./pages/Login.jsx";
import ReportingFormPage from "./pages/ReportingFormPage.jsx";
import SubmissionWorkspace from "./pages/SubmissionWorkspace.jsx";
import CaseCompletion from "./pages/CaseCompletion.jsx";
import QueueAcknowledgementPage from "./pages/QueueAcknowledgementPage.jsx";
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

// Clear temporary workflow values whenever the frontend boots. These values
// survive route changes, but a frontend restart starts a clean local session.
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
        <Route path="/patients/:patientId/case/:caseId/completion" element={<CaseCompletion />} />
        <Route path="/patients/:patientId/case/:caseId/queue" element={<QueueAcknowledgementPage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/cases/:caseId" element={<CaseWorkspacePage />} />
        <Route path="/cases/:caseId/reporting-form" element={<ReportingFormPage />} />
        <Route path="/cases/:caseId/completion" element={<CaseCompletion />} />
        <Route path="/cases/:caseId/queue" element={<QueueAcknowledgementPage />} />
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
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

