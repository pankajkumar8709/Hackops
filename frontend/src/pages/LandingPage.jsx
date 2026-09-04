import { Link } from 'react-router-dom';

export default function LandingPage() {
  return (
    <div className="landing-layout">
      <div className="landing-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">H</div>
          <span>HackOps</span>
        </div>
        <div className="flex gap-2">
          <Link to="/organizer/login" className="btn btn-ghost btn-sm">Organizer</Link>
        </div>
      </div>
      <div className="landing-hero">
        <div style={{ marginBottom: '32px', fontSize: '64px' }}>⚡</div>
        <h1 className="landing-hero-title">AI-Powered Hackathon<br />Operations Platform</h1>
        <p className="landing-hero-subtitle">
          Autonomous agent orchestration, real-time team management, and intelligent
          resource allocation — all in one platform.
        </p>
        <div className="landing-actions">
          <Link to="/signup" className="btn btn-primary btn-lg">
            Join as Participant →
          </Link>
          <Link to="/login" className="btn btn-secondary btn-lg">
            Participant Login
          </Link>
        </div>
        <div className="mt-6">
          <Link to="/organizer/login" className="btn btn-ghost btn-sm">
            🛠 Organizer Access
          </Link>
        </div>
      </div>
    </div>
  );
}
