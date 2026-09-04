import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchDashboardHealth, fetchEscalations, fetchAgentActions, fetchAllEvents, fetchAllDocuments, fetchAllTracks, createDashboardWS, exportSubmissionsCSV } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';

export default function DashboardPage() {
  const [health, setHealth] = useState(null);
  const [escalations, setEscalations] = useState([]);
  const [actions, setActions] = useState([]);
  const [events, setEvents] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [wsEvents, setWsEvents] = useState([]);
  const [wsStatus, setWsStatus] = useState('connecting');
  const [exporting, setExporting] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, e, a, ev, tr, doc] = await Promise.allSettled([
        fetchDashboardHealth(),
        fetchEscalations(),
        fetchAgentActions(10),
        fetchAllEvents(),
        fetchAllTracks(),
        fetchAllDocuments(),
      ]);
      if (h.status === 'fulfilled') setHealth(h.value);
      if (e.status === 'fulfilled') setEscalations(e.value);
      if (a.status === 'fulfilled') setActions(a.value);
      if (ev.status === 'fulfilled') setEvents(ev.value);
      if (tr.status === 'fulfilled') setTracks(tr.value);
      if (doc.status === 'fulfilled') setDocuments(doc.value);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // WebSocket for live updates — connection failures are surfaced, not silent.
  useEffect(() => {
    const ws = createDashboardWS({
      onMessage: (data) => {
        setWsEvents(prev => [data, ...prev].slice(0, 20));
        if (data.type === 'broadcast') toast(`Broadcast: ${data.message}`, 'info');
      },
      onStatus: setWsStatus,
    });
    return () => ws._cleanup?.();
  }, [toast]);

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportSubmissionsCSV();
      toast('Export downloaded!', 'success');
    } catch {
      toast('Export failed', 'error');
    } finally {
      setExporting(false);
    }
  };

  const setup = {
    event: events.length > 0,
    tracks: tracks.length > 0,
    mentors: (health?.mentors?.length || 0) > 0,
    resources: (health?.resource_pools?.length || 0) > 0,
    docs: documents.length > 0,
    participants: (health?.total_participants || 0) > 0,
  };
  const onboardingSteps = [
    { label: 'Create your event', done: setup.event, hint: 'Name it and set a submission deadline' },
    { label: 'Add tracks & requirements', done: setup.tracks, hint: 'What fields must submissions include?' },
    { label: 'Upload a rules document', done: setup.docs, hint: 'Pulse answers participant questions from this' },
    { label: 'Add mentors', done: setup.mentors, hint: 'Match participants with the right help' },
    { label: 'Add resource pools', done: setup.resources, hint: 'API keys, hardware, credits...' },
    { label: 'Invite participants', done: setup.participants, hint: 'They join via email + token' },
  ];
  const doneCount = onboardingSteps.filter(s => s.done).length;
  const needsOnboarding = setup.event === false && !loading;

  if (loading) return <LoadingSpinner text="Loading dashboard..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!health) return <EmptyState icon="📊" title="No data available" />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Real-time overview of your hackathon</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-secondary btn-sm" onClick={handleExport} disabled={exporting}>
            {exporting ? <><span className="loading-spinner" /> Exporting...</> : '📥 Export CSV'}
          </button>
          <button className="btn btn-primary btn-sm" onClick={load}>
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Live connection status — never fail silently into polling */}
      <div className="flex items-center gap-2 mb-4">
        {wsStatus === 'connected' ? (
          <span className="badge badge-success badge-dot">● Live updates connected</span>
        ) : wsStatus === 'error' || wsStatus === 'closed' ? (
          <span className="badge badge-warning badge-dot">● Live updates unavailable — showing snapshot (auto-refresh every 30s)</span>
        ) : (
          <span className="badge badge-neutral badge-dot">Connecting to live feed...</span>
        )}
      </div>

      {/* Onboarding checklist — replaces the empty dashboard with no explanation */}
      {needsOnboarding && (
        <section className="card mb-6" style={{ borderColor: 'var(--primary)', borderWidth: '1px' }}>
          <div className="card-header">
            <h2 className="card-title">Set up your event</h2>
            <button className="btn btn-primary btn-sm" onClick={() => navigate('/organizer/setup')}>
              Open Setup Wizard →
            </button>
          </div>
          <p className="text-sm text-muted mb-4">
            There's no event configured yet. {doneCount}/{onboardingSteps.length} steps complete — each checks off live as you finish it.
          </p>
          <div className="grid-2">
            {onboardingSteps.map(step => (
              <div key={step.label} className="flex items-start gap-2">
                <span className={`badge ${step.done ? 'badge-success' : 'badge-neutral'}`} style={{ minWidth: '24px', textAlign: 'center' }}>
                  {step.done ? '✓' : '•'}
                </span>
                <div>
                  <div className="text-sm font-semibold">{step.label}</div>
                  <div className="text-xs text-muted">{step.hint}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* KPI Cards */}
      <div className="dash-kpi-grid">
        <StatCard icon="👥" iconClass="primary" value={health.total_teams} label="Teams" />
        <StatCard icon="👤" iconClass="info" value={health.total_participants} label="Participants" />
        <StatCard icon="✅" iconClass="success" value={health.teams_ready} label="Teams Ready" />
        <StatCard icon="🚨" iconClass="error" value={health.open_escalations} label="Open Escalations" />
        <StatCard icon="🤖" iconClass="primary" value={health.total_agent_actions} label="Agent Actions" />
      </div>

      {/* Live Ticker */}
      {wsEvents.length > 0 && (
        <div className="card mb-6" style={{ padding: '12px 16px' }}>
          <div className="flex items-center gap-2" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            <span style={{ color: 'var(--success)', fontWeight: 600 }}>● LIVE</span>
            <span className="truncate">{wsEvents[0]?.type || 'update'} — {JSON.stringify(wsEvents[0]?.data || wsEvents[0]?.message || '').slice(0, 100)}</span>
          </div>
        </div>
      )}

      <div className="dash-sections">
        {/* Team Health Table */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Team Health</h2>
            <span className="text-sm text-muted">
              {health.teams?.length || 0} teams · Avg readiness {health.avg_readiness_pct}%
            </span>
          </div>
          {health.teams?.length > 0 ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Team</th>
                    <th>Status</th>
                    <th>Readiness</th>
                    <th>Members</th>
                    <th>Issues</th>
                  </tr>
                </thead>
                <tbody>
                  {health.teams.map(team => (
                    <tr key={team.id}>
                      <td className="table-cell-primary">{team.name}</td>
                      <td>
                        <StatusBadge status={team.submission_status} />
                      </td>
                      <td>
                        <div className="progress" style={{ minWidth: '120px' }}>
                          <div className="progress-bar">
                            <div
                              className={`progress-fill ${team.readiness_pct >= 100 ? 'success' : team.readiness_pct >= 50 ? 'warning' : 'error'}`}
                              style={{ width: `${Math.min(team.readiness_pct, 100)}%` }}
                            />
                          </div>
                          <span className="progress-text">{team.readiness_pct}%</span>
                        </div>
                      </td>
                      <td>{team.member_count}</td>
                      <td>
                        {team.open_issues > 0 ? (
                          <span className="badge badge-error">{team.open_issues}</span>
                        ) : (
                          <span className="badge badge-success">0</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon="👥" title="No teams yet" description="Teams will appear here once participants register." />
          )}
        </section>

        <div className="grid-2">
          {/* Recent Escalations */}
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Recent Escalations</h2>
              {escalations.length > 0 && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate('/organizer/escalations')}>
                  View All →
                </button>
              )}
            </div>
            {escalations.length > 0 ? (
              <div className="feed-list">
                {escalations.slice(0, 5).map(esc => (
                  <div key={esc.id} className="feed-item" style={{ borderLeftColor: 'var(--error)' }}>
                    <div className="feed-item-icon escalation">🚨</div>
                    <div className="feed-item-body">
                      <div className="feed-item-header">
                        <span className="feed-item-title">Urgency: {(esc.urgency_score * 100).toFixed(0)}%</span>
                        <span className="feed-item-time">{new Date(esc.created_at).toLocaleString()}</span>
                      </div>
                      {esc.issue && (
                        <div className="feed-item-desc">{esc.issue.description?.slice(0, 100)}</div>
                      )}
                      <div className="feed-item-meta">
                        <span className={`badge badge-dot ${esc.status === 'resolved' ? 'badge-success' : 'badge-error'}`}>
                          {esc.status}
                        </span>
                        <span className="badge badge-neutral">{esc.issue?.category}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState icon="🎉" title="No escalations" description="All clear!" />
            )}
          </section>

          {/* Recent Agent Actions */}
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Agent Activity</h2>
              {actions.length > 0 && (
                <button className="btn btn-ghost btn-sm" onClick={() => navigate('/organizer/agent')}>
                  View All →
                </button>
              )}
            </div>
            {actions.length > 0 ? (
              <div className="feed-list">
                {actions.slice(0, 5).map(action => (
                  <div key={action.id} className="feed-item">
                    <div className="feed-item-icon action">🤖</div>
                    <div className="feed-item-body">
                      <div className="feed-item-header">
                        <span className="feed-item-title">{action.action_type}</span>
                        <span className="feed-item-time">{new Date(action.executed_at).toLocaleString()}</span>
                      </div>
                      {action.summary && (
                        <div className="feed-item-desc" style={{ fontSize: '12px' }}>
                          {action.summary.slice(0, 140)}
                        </div>
                      )}
                      <div className="feed-item-meta">
                        <span className={`badge ${action.policy_check_result?.includes('ALLOWED') ? 'badge-success' : 'badge-warning'}`}>
                          {action.policy_check_result?.slice(0, 20) || 'N/A'}
                        </span>
                        {action.outcome && (
                          <span className="badge badge-neutral">{action.outcome.slice(0, 20)}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState icon="🤖" title="No agent actions yet" description="The orchestrator hasn't run yet." />
            )}
          </section>
        </div>

        {/* Resource Pools */}
        {health.resource_pools?.length > 0 && (
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Resource Pools</h2>
              <button className="btn btn-ghost btn-sm" onClick={() => navigate('/organizer/resources')}>
                Manage →
              </button>
            </div>
            <div className="resource-grid">
              {health.resource_pools.map(pool => {
                const pct = pool.total_quantity > 0
                  ? ((pool.total_quantity - pool.available_quantity) / pool.total_quantity * 100)
                  : 0;
                return (
                  <div key={pool.id} className="resource-card">
                    <div className="resource-card-header">
                      <span className="resource-card-name">{pool.name}</span>
                      {pool.available_quantity === 0 && <span className="badge badge-error">Out of Stock</span>}
                    </div>
                    <div className="resource-card-type">{pool.resource_type}</div>
                    <div className="resource-card-qty">
                      <span className="resource-qty-available">{pool.available_quantity}</span>
                      <span className="resource-qty-sep">/</span>
                      <span className="resource-qty-total">{pool.total_quantity}</span>
                    </div>
                    <div className="progress-bar">
                      <div
                        className={`progress-fill ${pct > 80 ? 'error' : pct > 50 ? 'warning' : 'success'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="text-xs text-muted mt-2">{pool.allocated_count} allocated</div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, iconClass, value, label }) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${iconClass}`}>{icon}</div>
      <div className="stat-body">
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = {
    submitted: 'success',
    in_progress: 'warning',
    not_submitted: 'neutral',
    under_review: 'info',
  };
  return (
    <span className={`badge badge-dot badge-${colors[status] || 'neutral'}`}>
      {status?.replace('_', ' ')}
    </span>
  );
}
