import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { loginParticipant } from '../api';
import { useToast } from '../components/ui/Toast';

export default function ParticipantLoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginParticipant(email.trim(), password);
      toast('Welcome back to HackOps!', 'success');
      navigate('/participant');
    } catch (err) {
      setError(err.message || 'Login failed — check your email and password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="sidebar-logo-icon">H</div>
          <span className="auth-logo-text">HackOps</span>
        </div>
        <h1 className="auth-title">Participant Login</h1>
        <p className="auth-subtitle">Sign in with your email and password.</p>

        {error && (
          <div className="alert alert-error mb-4" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="email">Registered Email</label>
            <input
              id="email"
              className="form-input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              autoFocus
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="form-input"
              type="password"
              placeholder="Your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary btn-full btn-lg"
            disabled={loading || !email.trim() || !password.trim()}
          >
            {loading ? <><span className="loading-spinner" /> Signing in...</> : 'Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          Don't have an account? <Link to="/signup">Sign up</Link>
          <br />
          <Link to="/organizer/login" className="mt-2" style={{ display: 'inline-block' }}>
            I'm an organizer →
          </Link>
          <br />
          <Link to="/" className="mt-2" style={{ display: 'inline-block' }}>← Back to Home</Link>
        </div>
      </div>
    </div>
  );
}
