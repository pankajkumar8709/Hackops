import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { loginOrganizer } from '../api';
import { useToast } from '../components/ui/Toast';

export default function OrganizerLoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPw, setShowPw] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginOrganizer(username, password);
      toast('Welcome back, Organizer!', 'success');
      navigate('/organizer');
    } catch (err) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-shell">
        <aside className="auth-showcase">
          <div className="auth-showcase-brand"><span className="auth-showcase-mark">H</span> HackOps</div>
          <div className="auth-showcase-copy">
            <div className="auth-showcase-eyebrow">Organizer console</div>
            <h2 className="auth-showcase-title">The event room, beautifully organized.</h2>
            <p className="auth-showcase-description">See the pulse of your hackathon, unblock teams early, and make every participant feel looked after.</p>
          </div>
          <div className="auth-showcase-note"><span className="auth-showcase-note-dot" /> Everything in its right place</div>
        </aside>
      <div className="auth-card">
        <div className="auth-logo">
          <div className="sidebar-logo-icon">H</div>
          <span className="auth-logo-text">HackOps</span>
        </div>
        <h1 className="auth-title">Organizer Login</h1>
        <p className="auth-subtitle">Sign in to manage your hackathon</p>

        {error && <div className="alert alert-error mb-4">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="username">Username</label>
            <input
              id="username"
              className="form-input"
              type="text"
              placeholder="Enter username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <div className="form-input-group">
              <input
                id="password"
                className="form-input"
                type={showPw ? 'text' : 'password'}
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="btn btn-ghost btn-icon"
                style={{ position: 'absolute', right: '4px', top: '50%', transform: 'translateY(-50%)' }}
                onClick={() => setShowPw(!showPw)}
                tabIndex={-1}
              >
                {showPw ? '🙈' : '👁'}
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="btn btn-primary btn-full btn-lg"
            disabled={loading}
          >
            {loading ? <><span className="loading-spinner" /> Signing in...</> : 'Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          <Link to="/login" className="mt-2" style={{ display: 'inline-block' }}>
            I'm a participant →
          </Link>
          <br />
          <Link to="/" className="mt-2" style={{ display: 'inline-block' }}>← Back to Home</Link>
        </div>
      </div>
      </div>
    </div>
  );
}
