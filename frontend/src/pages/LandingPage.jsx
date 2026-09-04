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
          <Link to="/organizer/login" className="btn btn-ghost btn-sm">Organizer access</Link>
          <Link to="/login" className="btn btn-secondary btn-sm">Sign in</Link>
        </div>
      </div>
      <div className="landing-hero">
        <section className="landing-panel">
          <div className="landing-kicker"><span>✦</span> The calmer way to run a hackathon</div>
          <h1 className="landing-hero-title">Create an event people <span className="landing-highlight">remember.</span></h1>
          <p className="landing-hero-subtitle">
            Give teams, mentors, and organizers one thoughtful home for every moment that matters.
          </p>
          <div className="landing-actions">
            <Link to="/signup" className="btn btn-primary btn-lg">Join as a participant</Link>
            <Link to="/login" className="btn btn-secondary btn-lg">I already have an account</Link>
          </div>
          <div className="landing-metrics" aria-label="HackOps platform benefits">
            <div className="landing-metric"><div className="landing-metric-value">One place</div><div className="landing-metric-label">for people, projects, and help</div></div>
            <div className="landing-metric"><div className="landing-metric-value">Live pulse</div><div className="landing-metric-label">for every important moment</div></div>
          </div>
        </section>
        <aside className="landing-preview" aria-label="HackOps workspace preview">
          <div className="landing-preview-card">
            <div className="landing-preview-header">
              <div><div className="text-xs text-muted">EVENT WORKSPACE</div><div className="landing-preview-title">BuildFest 2026</div></div>
              <span className="badge badge-success badge-dot">Live</span>
            </div>
            <div className="landing-preview-list">
              <div className="landing-preview-row"><span className="avatar">A</span><span><strong>Team Atlas</strong><br /><span className="text-xs text-muted">Looking for a designer</span></span><span className="landing-preview-pill info">Match</span></div>
              <div className="landing-preview-row"><span className="avatar">M</span><span><strong>Mentor hours</strong><br /><span className="text-xs text-muted">2 new slots available</span></span><span className="landing-preview-pill success">Open</span></div>
              <div className="landing-preview-row"><span className="avatar">!</span><span><strong>Submission check</strong><br /><span className="text-xs text-muted">Project details ready</span></span><span className="landing-preview-pill warning">Review</span></div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
