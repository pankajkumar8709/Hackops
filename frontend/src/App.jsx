import { Routes, Route, Navigate } from 'react-router-dom'
import HealthPage from './pages/HealthPage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ParticipantLoginPage from './pages/ParticipantLoginPage'
import ParticipantLayout from './pages/ParticipantLayout'
import ParticipantTeamPage from './pages/ParticipantTeamPage'
import ParticipantChatPage from './pages/ParticipantChatPage'
import ParticipantMatchesPage from './pages/ParticipantMatchesPage'
import { getToken } from './api'

function PrivateRoute({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HealthPage />} />
      {/* Organizer routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <DashboardPage />
          </PrivateRoute>
        }
      />
      {/* Participant routes */}
      <Route path="/participant/login" element={<ParticipantLoginPage />} />
      <Route path="/participant" element={<ParticipantLayout />}>
        <Route path="team" element={<ParticipantTeamPage />} />
        <Route path="chat" element={<ParticipantChatPage />} />
        <Route path="matches" element={<ParticipantMatchesPage />} />
        <Route index element={<Navigate to="/participant/team" replace />} />
      </Route>
    </Routes>
  )
}
