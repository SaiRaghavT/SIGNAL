import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Patients from "./pages/Patients.jsx";
import PatientWorkspace from "./pages/PatientWorkspace.jsx";
import { CasesPage } from "./pages/CasesPage.jsx";
import CaseWorkspacePage from "./pages/CaseWorkspacePage.jsx";
import { SubmissionsPage } from "./pages/SubmissionsPage.jsx";
import { FollowupsPage } from "./pages/FollowupsPage.jsx";
import { AnalyticsPage } from "./pages/AnalyticsPage.jsx";
import { AuditPage } from "./pages/AuditPage.jsx";
import Login from "./pages/Login.jsx";
import ReportingFormPage from "./pages/ReportingFormPage.jsx";
import SubmissionWorkspace from "./pages/SubmissionWorkspace.jsx";
import FollowUpWorkspace from "./pages/FollowUpWorkspace.jsx";
import CaseCompletion from "./pages/CaseCompletion.jsx";

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
      <Route path="/patients/:patientId/case/:caseId/follow-up" element={<FollowUpWorkspace />} />
      <Route path="/patients/:patientId/case/:caseId/completion" element={<CaseCompletion />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/cases/:caseId" element={<CaseWorkspacePage />} />
        <Route path="/cases/:caseId/reporting-form" element={<ReportingFormPage />} />
        <Route path="/cases/:caseId/completion" element={<CaseCompletion />} />
        <Route path="/submissions" element={<SubmissionsPage />} />
        <Route path="/submissions/case/:caseId" element={<SubmissionWorkspace />} />
        <Route path="/follow-ups/case/:caseId" element={<FollowUpWorkspace />} />
        <Route path="/cases/:caseId/follow-up" element={<FollowupsPage />} />
        <Route path="/follow-ups" element={<FollowupsPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
