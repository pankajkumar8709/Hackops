import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { getToken, clearToken, fetchMyProfile } from '../api'

const NAV_ITEMS = [
  { to: '/participant/team', label: '🏠 Team Status', icon: '🏠' },
  { to: '/participant/chat', label: '💬 Chat', icon: '💬' },
  { to: '/participant/matches', label: '🤝 Matches', icon: '🤝' },
]

export default function ParticipantLayout() {
  const [profile, setProfile] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!getToken()) {
      navigate('/participant/login')
      return
    }
    fetchMyProfile()
      .then(setProfile)
      .catch(() => {
        clearToken()
        navigate('/participant/login')
      })
  }, [navigate])

  function handleLogout() {
    clearToken()
    navigate('/participant/login')
  }

  return (
    <div className="participant-layout">
      {/* Sidebar */}
      <aside className="p-sidebar">
        <div className="p-sidebar-header">
          <span className="p-logo">⚡ Pulse</span>
          {profile && (
            <div className="p-user-info">
              <span className="p-user-name">{profile.name}</span>
              <span className="p-user-role">Participant</span>
            </div>
          )}
        </div>
        <nav className="p-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `p-nav-link ${isActive ? 'active' : ''}`}
            >
              <span className="p-nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <button className="p-logout-btn" onClick={handleLogout}>
          ↩ Logout
        </button>
      </aside>

      {/* Main content */}
      <main className="p-main">
        <Outlet />
      </main>
    </div>
  )
}
