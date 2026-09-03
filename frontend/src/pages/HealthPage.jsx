import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

export default function HealthPage() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setStatus(data))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div style={{
      fontFamily: 'sans-serif', padding: '3rem',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      minHeight: '100vh', background: '#0f0f0f', color: '#e0e0e0',
    }}>
      <h1 style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>⚡ Pulse</h1>
      <p style={{ color: '#888', marginBottom: '2rem' }}>
        Autonomous Hackathon Concierge & Event Operations Agent
      </p>

      {/* Backend status */}
      <div style={{
        background: '#1a1a2e', borderRadius: 12, padding: '1.5rem 2rem',
        marginBottom: '2rem', textAlign: 'center', minWidth: 300,
      }}>
        <p style={{ color: '#888', marginBottom: '0.5rem' }}>Backend Status</p>
        {error ? (
          <p style={{ color: '#ef4444', fontWeight: 700 }}>ERROR — {error}</p>
        ) : status ? (
          <div>
            <p style={{ color: '#10b981', fontWeight: 700, fontSize: '1.2rem' }}>
              ✅ {status.status?.toUpperCase() || 'OK'}
            </p>
            <p style={{ color: '#666', fontSize: '0.85rem' }}>
              v{status.version} • {status.service}
            </p>
          </div>
        ) : (
          <p style={{ color: '#888' }}>Checking…</p>
        )}
      </div>

      {/* Navigation */}
      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        <Link to="/login" style={linkStyle}>
          <span style={{ fontSize: '2rem' }}>🔧</span>
          <span style={{ fontWeight: 600 }}>Organizer Dashboard</span>
          <span style={{ fontSize: '0.8rem', color: '#888' }}>Manage events, teams, escalations</span>
        </Link>
        <Link to="/participant/login" style={linkStyle}>
          <span style={{ fontSize: '2rem' }}>🧑</span>
          <span style={{ fontWeight: 600 }}>Participant Portal</span>
          <span style={{ fontSize: '0.8rem', color: '#888' }}>Chat, team status, match suggestions</span>
        </Link>
      </div>
    </div>
  )
}

const linkStyle = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem',
  background: '#1a1a2e', borderRadius: 12, padding: '1.5rem 2rem',
  textDecoration: 'none', color: '#e0e0e0', minWidth: 220,
  border: '1px solid #333', transition: 'border-color 0.2s',
}
