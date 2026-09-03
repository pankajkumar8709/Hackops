import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { setToken, fetchMyProfile } from '../api'

export default function ParticipantLoginPage() {
  const [tokenInput, setTokenInput] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleTokenLogin(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      setToken(tokenInput.trim())
      // Validate token by fetching profile
      await fetchMyProfile()
      navigate('/participant/team')
    } catch (err) {
      setError('Invalid token. Please check and try again.')
      setToken(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>⚡ Pulse</h1>
          <p>Hackathon Concierge — Participant Login</p>
        </div>
        <form onSubmit={handleTokenLogin}>
          <div className="form-group">
            <label>Your Token</label>
            <input
              type="text"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="Paste your participant token here"
              required
              autoFocus
            />
            <span className="form-hint">You received this token when you registered.</span>
          </div>
          {error && <div className="form-error">{error}</div>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
