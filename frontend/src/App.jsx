import { Routes, Route, Navigate } from 'react-router-dom'
import HealthPage from './pages/HealthPage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import { getToken } from './api'

function PrivateRoute({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HealthPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <DashboardPage />
          </PrivateRoute>
        }
      />
    </Routes>
  )
}
