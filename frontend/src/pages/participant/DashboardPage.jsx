import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fetchMyProfile, fetchMyTeam, fetchMySubmission, fetchMyIssues, fetchMyNotifications, fetchMyResourceAllocations } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';

export default function ParticipantDashboard() {
  const [profile, setProfile] = useState(null);
  const [team, setTeam] = useState(null);
  const [submission, setSubmission] = useState(null);
  const [issues, setIssues] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.allSettled([
        fetchMyProfile(),
        fetchMyTeam(),
        fetchMySubmission(),
        fetchMyIssues(),
        fetchMyNotifications(),
        fetchMyResourceAllocations(),
      ]);
      if (results[0].status === 'fulfilled') setProfile(results[0].value);
      if (results[1].status === 'fulfilled') setTeam(results[1].value);
      if (results[2].status === 'fulfilled') setSubmission(results[2].value);
      if (results[3].status === 'fulfilled') setIssues(results[3].value);
      if (results[4].status === 'fulfilled') setNotifications(results[4].value);
      if (results[5].status === 'fulfilled') setResources(results[5].value);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingSpinner text="Loading your dashboard..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const unreadNotifs = notifications.filter(n => !n.read);
  const openIssues = issues.filter(i => i.status !== 'resolved');

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Welcome back, {profile?.name || 'Hacker'} 👋</h1>
          <p className="page-subtitle">{team ? `Team: ${team.name}` : 'No team yet'}</p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid-stats mb-6">
        <div className="stat-card">
          <div className="stat-icon primary">👥</div>
          <div className="stat-body">
            <div className="stat-value">{team?.name || '—'}</div>
            <div className="stat-label">My Team</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon success">📊</div>
          <div className="stat-body">
            <div className="stat-value">{team?.readiness_pct || 0}%</div>
            <div className="stat-label">Readiness</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon info">📋</div>
          <div className="stat-body">
            <div className="stat-value">{submission ? `${submission.completeness_pct}%` : 'None'}</div>
            <div className="stat-label">Submission</div>
          </div>
        </div>
        <div className="stat-card">
          <div className={`stat-icon ${openIssues.length > 0 ? 'error' : 'success'}`}>🐛</div>
          <div className="stat-body">
            <div className="stat-value">{openIssues.length}</div>
            <div className="stat-label">Open Issues</div>
          </div>
        </div>
        <div className="stat-card">
          <div className={`stat-icon ${unreadNotifs.length > 0 ? 'warning' : 'success'}`}>🔔</div>
          <div className="stat-body">
            <div className="stat-value">{unreadNotifs.length}</div>
            <div className="stat-label">Unread</div>
          </div>
        </div>
      </div>

      {/* Readiness Progress */}
      {team && (
        <div className="card mb-6">
          <div className="card-header">
            <h2 className="card-title">Team Readiness</h2>
          </div>
          <div className="progress mb-2">
            <div className="progress-bar" style={{ height: '10px' }}>
              <div
                className={`progress-fill ${team.readiness_pct >= 100 ? 'success' : team.readiness_pct >= 50 ? 'warning' : 'error'}`}
                style={{ width: `${Math.min(team.readiness_pct, 100)}%` }}
              />
            </div>
            <span className="progress-text" style={{ fontSize: '14px' }}>{team.readiness_pct}%</span>
          </div>
          <span className="text-xs text-muted">Status: {team.submission_status?.replace('_', ' ')}</span>
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid-3 mb-6">
        <Link to="/participant/chat" className="card" style={{ textDecoration: 'none', cursor: 'pointer', transition: 'border-color 0.15s', border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>💬</div>
          <div className="font-semibold">AI Assistant</div>
          <div className="text-sm text-muted mt-1">Ask questions about the hackathon</div>
        </Link>
        <Link to="/participant/submission" className="card" style={{ textDecoration: 'none', cursor: 'pointer', transition: 'border-color 0.15s', border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>📋</div>
          <div className="font-semibold">Submission</div>
          <div className="text-sm text-muted mt-1">{submission ? 'Update your submission' : 'Submit your project'}</div>
        </Link>
        <Link to="/participant/matches" className="card" style={{ textDecoration: 'none', cursor: 'pointer', transition: 'border-color 0.15s', border: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>🎯</div>
          <div className="font-semibold">Match Suggestions</div>
          <div className="text-sm text-muted mt-1">Find teammates and mentors</div>
        </Link>
      </div>

      {/* Recent Issues & Notifications */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Recent Issues</h2>
            {openIssues.length > 0 && <span className="badge badge-error">{openIssues.length}</span>}
          </div>
          {openIssues.length === 0 ? (
            <div className="text-sm text-muted">No open issues 🎉</div>
          ) : (
            <div className="flex flex-col gap-2">
              {openIssues.slice(0, 3).map(issue => (
                <div key={issue.id} className="feed-item" style={{ borderLeftColor: issue.severity > 0.7 ? 'var(--error)' : 'var(--warning)' }}>
                  <div className="feed-item-body">
                    <div className="text-sm">{issue.description?.slice(0, 100)}</div>
                    <div className="flex gap-1 mt-1">
                      <span className="badge badge-neutral">{issue.category}</span>
                      <span className="badge badge-neutral">{issue.status}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Notifications</h2>
            {unreadNotifs.length > 0 && <span className="badge badge-primary">{unreadNotifs.length} new</span>}
          </div>
          {notifications.length === 0 ? (
            <div className="text-sm text-muted">No notifications yet</div>
          ) : (
            <div className="flex flex-col gap-2">
              {notifications.slice(0, 4).map(n => (
                <div key={n.id} className="text-sm" style={{ padding: '8px', background: n.read ? 'transparent' : 'var(--primary-muted)', borderRadius: 'var(--radius-md)' }}>
                  <div>{n.content?.slice(0, 100)}</div>
                  <div className="text-xs text-muted mt-1">{new Date(n.sent_at).toLocaleString()}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
