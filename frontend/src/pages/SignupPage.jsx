import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { registerParticipant } from '../api';
import { useToast } from '../components/ui/Toast';

const SKILL_OPTIONS = [
  'React', 'Vue', 'Angular', 'Node.js', 'Python', 'Go', 'Rust',
  'TypeScript', 'JavaScript', 'Java', 'C++', 'Swift',
  'Machine Learning', 'Data Science', 'DevOps', 'UI/UX',
  'Blockchain', 'Cloud', 'AWS', 'Docker', 'PostgreSQL', 'MongoDB',
  'FastAPI', 'Django', 'Flask', 'Express',
];

export default function SignupPage() {
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    skills: [],
    track_pref: '',
    discord_handle: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const toast = useToast();

  const update = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const toggleSkill = (skill) => {
    setForm(prev => ({
      ...prev,
      skills: prev.skills.includes(skill)
        ? prev.skills.filter(s => s !== skill)
        : [...prev.skills, skill],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await registerParticipant(form);
      toast('Account created! Please sign in.', 'success');
      navigate('/login');
    } catch (err) {
      setError(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-card" style={{ maxWidth: '500px' }}>
        <div className="auth-logo">
          <div className="sidebar-logo-icon">H</div>
          <span className="auth-logo-text">HackOps</span>
        </div>
        <h1 className="auth-title">Join the Hackathon</h1>
        <p className="auth-subtitle">Create your participant account</p>

        {error && <div className="alert alert-error mb-4">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="name">Full Name *</label>
            <input
              id="name"
              className="form-input"
              type="text"
              placeholder="Your name"
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="email">Email *</label>
            <input
              id="email"
              className="form-input"
              type="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={(e) => update('email', e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password *</label>
            <input
              id="password"
              className="form-input"
              type="password"
              placeholder="At least 8 characters"
              value={form.password}
              onChange={(e) => update('password', e.target.value)}
              required
              minLength={8}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Your Skills</label>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '6px',
              padding: '8px',
              background: 'var(--bg-base)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)',
              minHeight: '44px',
            }}>
              {SKILL_OPTIONS.map(skill => (
                <button
                  key={skill}
                  type="button"
                  className={`tag ${form.skills.includes(skill) ? 'badge badge-primary' : ''}`}
                  style={{
                    cursor: 'pointer',
                    border: form.skills.includes(skill) ? 'none' : '1px solid var(--border-subtle)',
                    background: form.skills.includes(skill) ? undefined : 'transparent',
                    color: form.skills.includes(skill) ? undefined : 'var(--text-secondary)',
                  }}
                  onClick={() => toggleSkill(skill)}
                >
                  {skill}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="track_pref">Preferred Track</label>
            <select
              id="track_pref"
              className="form-input form-select"
              value={form.track_pref}
              onChange={(e) => update('track_pref', e.target.value)}
            >
              <option value="">No preference</option>
              <option value="AI & Machine Learning">AI & Machine Learning</option>
              <option value="Web & Fullstack">Web & Fullstack</option>
              <option value="Hardware & IoT">Hardware & IoT</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="discord">Discord Handle</label>
            <input
              id="discord"
              className="form-input"
              type="text"
              placeholder="username#0000 (optional)"
              value={form.discord_handle}
              onChange={(e) => update('discord_handle', e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full btn-lg"
            disabled={loading || !form.name.trim() || !form.email.trim() || !form.password.trim()}
          >
            {loading ? <><span className="loading-spinner" /> Creating Account...</> : 'Create Account'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Log in</Link>
          <br />
          <Link to="/" className="mt-2" style={{ display: 'inline-block' }}>← Back to Home</Link>
        </div>
      </div>
    </div>
  );
}


