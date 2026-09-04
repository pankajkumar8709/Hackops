import { Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './components/ui/Toast';
import DashboardLayout from './components/layout/DashboardLayout';

// Auth Pages
import LandingPage from './pages/LandingPage';
import OrganizerLoginPage from './pages/OrganizerLoginPage';
import ParticipantLoginPage from './pages/ParticipantLoginPage';
import SignupPage from './pages/SignupPage';

// Organizer Pages
import DashboardPage from './pages/organizer/DashboardPage';
import ParticipantsPage from './pages/organizer/ParticipantsPage';
import TeamsPage from './pages/organizer/TeamsPage';
import SubmissionsPage from './pages/organizer/SubmissionsPage';
import MentorsPage from './pages/organizer/MentorsPage';
import ResourcesPage from './pages/organizer/ResourcesPage';
import EscalationsPage from './pages/organizer/EscalationsPage';
import AgentActivityPage from './pages/organizer/AgentActivityPage';
import ApprovalsPage from './pages/organizer/ApprovalsPage';
import NotificationsPage from './pages/organizer/NotificationsPage';
import SetupPage from './pages/organizer/SetupPage';

// Participant Pages
import ParticipantDashboard from './pages/participant/DashboardPage';
import ParticipantTeamPage from './pages/participant/TeamPage';
import ParticipantSubmissionPage from './pages/participant/SubmissionPage';
import ParticipantChatPage from './pages/participant/ChatPage';
import ParticipantMatchesPage from './pages/participant/MatchesPage';
import ParticipantIssuesPage from './pages/participant/IssuesPage';
import ParticipantResourcesPage from './pages/participant/ResourcesPage';
import ParticipantNotificationsPage from './pages/participant/NotificationsPage';

import { getToken, isOrganizer, isParticipant, clearToken } from './api';

// Validate a stored token actually authorizes the requested role. If the
// wrong role's token is present we clear it and redirect to the matching
// login — a participant JWT can never render an organizer page (and the
// backend would 403 it anyway) and vice-versa.
function OrganizerRoute({ children }) {
  const token = getToken();
  if (!token) return <Navigate to="/organizer/login" replace />;
  if (!isOrganizer()) {
    clearToken();
    return <Navigate to="/organizer/login" replace />;
  }
  return children;
}

function ParticipantRoute({ children }) {
  const token = getToken();
  if (!token) return <Navigate to="/login" replace />;
  if (!isParticipant()) {
    clearToken();
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        {/* Public */}
        <Route path="/" element={<LandingPage />} />

        {/* Auth */}
        <Route path="/organizer/login" element={<OrganizerLoginPage />} />
        <Route path="/login" element={<ParticipantLoginPage />} />
        <Route path="/signup" element={<SignupPage />} />

        {/* Organizer Dashboard */}
        <Route path="/organizer" element={
          <OrganizerRoute>
            <DashboardLayout title="HackOps" />
          </OrganizerRoute>
        }>
          <Route index element={<DashboardPage />} />
          <Route path="setup" element={<SetupPage />} />
          <Route path="participants" element={<ParticipantsPage />} />
          <Route path="teams" element={<TeamsPage />} />
          <Route path="submissions" element={<SubmissionsPage />} />
          <Route path="mentors" element={<MentorsPage />} />
          <Route path="resources" element={<ResourcesPage />} />
          <Route path="escalations" element={<EscalationsPage />} />
          <Route path="agent" element={<AgentActivityPage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
        </Route>

        {/* Participant Dashboard */}
        <Route path="/participant" element={
          <ParticipantRoute>
            <DashboardLayout title="HackOps" />
          </ParticipantRoute>
        }>
          <Route index element={<ParticipantDashboard />} />
          <Route path="team" element={<ParticipantTeamPage />} />
          <Route path="submission" element={<ParticipantSubmissionPage />} />
          <Route path="chat" element={<ParticipantChatPage />} />
          <Route path="matches" element={<ParticipantMatchesPage />} />
          <Route path="issues" element={<ParticipantIssuesPage />} />
          <Route path="resources" element={<ParticipantResourcesPage />} />
          <Route path="notifications" element={<ParticipantNotificationsPage />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ToastProvider>
  );
}
