import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell.jsx";
import { DashboardPage } from "./pages/Dashboard.jsx";
import InformationReceived from "./pages/InformationReceived.jsx";
import Patients from "./pages/Patients.jsx";
import PatientWorkspace from "./pages/PatientWorkspace.jsx";
import { CandidatesPage } from "./pages/CandidatesPage.jsx";
import { CasesPage } from "./pages/CasesPage.jsx";
import { CaseWorkspacePage } from "./pages/CaseWorkspacePage.jsx";
import { SubmissionsPage } from "./pages/SubmissionsPage.jsx";
import { FollowupsPage } from "./pages/FollowupsPage.jsx";
import { AnalyticsPage } from "./pages/AnalyticsPage.jsx";
import { AuditPage } from "./pages/AuditPage.jsx";
import Login from "./pages/Login.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/information" element={<InformationReceived />} />
        <Route path="/patients" element={<Patients />} />
        <Route path="/patients/:patientId" element={<PatientWorkspace />} />
        <Route path="/candidates" element={<CandidatesPage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/cases/:caseId" element={<CaseWorkspacePage />} />
        <Route path="/submissions" element={<SubmissionsPage />} />
        <Route path="/follow-ups" element={<FollowupsPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
