import { useState, useEffect, useCallback, useRef } from 'react'
import {
  fetchDashboardHealth,
  fetchEscalations,
  fetchApprovalQueue,
  fetchAgentActions,
  resolveEscalation,
  broadcastMessage,
  overrideTeam,
  overrideSubmission,
  exportSubmissionsCSV,
  runSweep,
  createDashboardWS,
  clearToken,
} from '../api'

// ─── Stats Card ──────────────────────────────────────────

function StatsCard({ label, value, color, icon }) {
  return (
    <div className="stats-card" style={{ borderLeftColor: color }}>
      <div className="stats-icon">{icon}</div>
      <div className="stats-body">
        <span className="stats-value">{value}</span>
        <span className="stats-label">{label}</span>
      </div>
    </div>
  )
}

// ─── Tab Panel ───────────────────────────────────────────

function TabPanel({ tabs, activeTab, onTabChange }) {
  return (
    <div className="tab-bar">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.icon} {tab.label}
          {tab.count !== undefined && (
            <span className="tab-count">{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}

// ─── Health Panel ────────────────────────────────────────

function HealthPanel({ health }) {
  if (!health) return <div className="panel-loading">Loading health data…</div>

  return (
    <div className="panel">
      {/* Stats row */}
      <div className="stats-grid">
        <StatsCard label="Teams" value={health.total_teams} color="#6366f1" icon="👥" />
        <StatsCard label="Ready" value={health.teams_ready} color="#10b981" icon="✅" />
        <StatsCard label="Avg Readiness" value={`${health.avg_readiness_pct}%`} color="#f59e0b" icon="📊" />
        <StatsCard label="Participants" value={health.total_participants} color="#8b5cf6" icon="🧑" />
        <StatsCard label="Open Escalations" value={health.open_escalations} color="#ef4444" icon="🚨" />
        <StatsCard label="Agent Actions" value={health.total_agent_actions} color="#3b82f6" icon="🤖" />
        <StatsCard label="Notifications" value={health.total_notifications} color="#ec4899" icon="🔔" />
        <StatsCard label="Submissions" value={health.total_submissions} color="#14b8a6" icon="📦" />
      </div>

      {/* Teams table */}
      <h3 className="section-title">Team Readiness</h3>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Team</th>
              <th>Members</th>
              <th>Status</th>
              <th>Readiness</th>
              <th>Open Issues</th>
            </tr>
          </thead>
          <tbody>
            {health.teams.map((team) => (
              <tr key={team.id}>
                <td className="font-medium">{team.name}</td>
                <td>{team.member_count}</td>
                <td>
                  <span className={`badge badge-${team.submission_status === 'submitted' ? 'green' : 'gray'}`}>
                    {team.submission_status}
                  </span>
                </td>
                <td>
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${team.readiness_pct}%`,
                        backgroundColor: team.readiness_pct >= 100 ? '#10b981' : team.readiness_pct > 50 ? '#f59e0b' : '#ef4444',
                      }}
                    />
                  </div>
                  <span className="progress-text">{team.readiness_pct}%</span>
                </td>
                <td>
                  {team.open_issues > 0 ? (
                    <span className="badge badge-red">{team.open_issues}</span>
                  ) : (
                    <span className="badge badge-green">0</span>
                  )}
                </td>
              </tr>
            ))}
            {health.teams.length === 0 && (
              <tr><td colSpan={5} className="empty-row">No teams yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mentors */}
      <h3 className="section-title">Mentor Load</h3>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Mentor</th>
              <th>Skills</th>
              <th>Availability</th>
              <th>Active Allocations</th>
            </tr>
          </thead>
          <tbody>
            {health.mentors.map((m) => (
              <tr key={m.id}>
                <td className="font-medium">{m.name}</td>
                <td>{m.skills.join(', ') || '—'}</td>
                <td>
                  <span className={`badge badge-${m.availability_status === 'available' ? 'green' : m.availability_status === 'busy' ? 'yellow' : 'gray'}`}>
                    {m.availability_status}
                  </span>
                </td>
                <td>{m.active_allocations}</td>
              </tr>
            ))}
            {health.mentors.length === 0 && (
              <tr><td colSpan={4} className="empty-row">No mentors</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Resource Pools */}
      <h3 className="section-title">Resource Pools</h3>
      <div className="resource-grid">
        {health.resource_pools.map((pool) => (
          <div key={pool.id} className="resource-card">
            <div className="resource-header">
              <span className="resource-name">{pool.name}</span>
              <span className="badge badge-blue">{pool.resource_type}</span>
            </div>
            <div className="resource-quantities">
              <span className="qty-available">{pool.available_quantity}</span>
              <span className="qty-separator">/</span>
              <span className="qty-total">{pool.total_quantity}</span>
            </div>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${pool.total_quantity > 0 ? (pool.available_quantity / pool.total_quantity) * 100 : 0}%`,
                  backgroundColor: pool.available_quantity === 0 ? '#ef4444' : '#10b981',
                }}
              />
            </div>
          </div>
        ))}
        {health.resource_pools.length === 0 && (
          <div className="empty-row">No resource pools</div>
        )}
      </div>
    </div>
  )
}

// ─── Escalation Queue Panel ──────────────────────────────

function EscalationPanel({ escalations, onResolve }) {
  if (!escalations) return <div className="panel-loading">Loading escalations…</div>

  return (
    <div className="panel">
      {escalations.length === 0 ? (
        <div className="empty-state">🎉 No open escalations</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Urgency</th>
                <th>Issue</th>
                <th>Severity</th>
                <th>Blocking</th>
                <th>Status</th>
                <th>Assigned</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {escalations.map((esc) => (
                <tr key={esc.id}>
                  <td>
                    <span className={`urgency urgency-${esc.urgency_score > 0.7 ? 'high' : esc.urgency_score > 0.4 ? 'medium' : 'low'}`}>
                      {esc.urgency_score.toFixed(2)}
                    </span>
                  </td>
                  <td className="font-medium max-w-300">
                    {esc.issue?.description?.slice(0, 80) || '—'}
                  </td>
                  <td>{esc.issue?.severity || '—'}</td>
                  <td>{esc.issue?.is_blocking ? '🔴 Yes' : '—'}</td>
                  <td>
                    <span className={`badge badge-${esc.status === 'open' ? 'red' : esc.status === 'resolved' ? 'green' : 'yellow'}`}>
                      {esc.status}
                    </span>
                  </td>
                  <td>{esc.assigned_organizer || '—'}</td>
                  <td>
                    {esc.status === 'open' && (
                      <button
                        className="btn-sm btn-green"
                        onClick={() => onResolve(esc.id)}
                      >
                        Resolve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ─── Approval Queue Panel ────────────────────────────────

function ApprovalPanel({ queue }) {
  if (!queue) return <div className="panel-loading">Loading approval queue…</div>

  return (
    <div className="panel">
      {queue.total_pending === 0 ? (
        <div className="empty-state">✅ No pending approvals</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Description</th>
                <th>Reasoning</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {queue.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <span className="badge badge-blue">{item.action_type}</span>
                  </td>
                  <td className="font-medium">{item.description}</td>
                  <td className="text-sm max-w-300">{item.reasoning || '—'}</td>
                  <td>
                    <span className={`badge badge-${item.status === 'pending' ? 'yellow' : 'green'}`}>
                      {item.status}
                    </span>
                  </td>
                  <td className="text-sm">{new Date(item.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ─── Explainability Feed Panel ───────────────────────────

function ExplainabilityPanel({ actions }) {
  if (!actions) return <div className="panel-loading">Loading agent actions…</div>

  return (
    <div className="panel">
      {actions.length === 0 ? (
        <div className="empty-state">🤖 No agent actions logged yet</div>
      ) : (
        <div className="feed-list">
          {actions.map((action) => (
            <div key={action.id} className="feed-item">
              <div className="feed-icon">🤖</div>
              <div className="feed-body">
                <div className="feed-header">
                  <span className="badge badge-blue">{action.action_type}</span>
                  <span className="feed-time">{new Date(action.executed_at).toLocaleString()}</span>
                </div>
                {action.reasoning_trace && (
                  <div className="feed-reasoning">{action.reasoning_trace}</div>
                )}
                {action.policy_check_result && (
                  <div className="feed-policy">Policy: {action.policy_check_result}</div>
                )}
                {action.outcome && (
                  <div className="feed-outcome">Outcome: {action.outcome}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Override Panel ──────────────────────────────────────

function OverridePanel({ health, onOverride }) {
  const [selectedTeam, setSelectedTeam] = useState(null)
  const [statusVal, setStatusVal] = useState('')
  const [readinessVal, setReadinessVal] = useState('')
  const [result, setResult] = useState(null)

  async function handleOverride() {
    if (!selectedTeam) return
    const data = {}
    if (statusVal) data.submission_status = statusVal
    if (readinessVal !== '') data.readiness_pct = parseFloat(readinessVal)
    try {
      const res = await overrideTeam(selectedTeam, data)
      setResult(res)
      onOverride()
    } catch (err) {
      setResult({ error: err.message })
    }
  }

  return (
    <div className="panel">
      <h3 className="section-title">Manual Override</h3>
      <div className="override-form">
        <div className="form-row">
          <div className="form-group">
            <label>Team</label>
            <select
              value={selectedTeam || ''}
              onChange={(e) => setSelectedTeam(e.target.value)}
            >
              <option value="">Select team…</option>
              {health?.teams.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Submission Status</label>
            <select value={statusVal} onChange={(e) => setStatusVal(e.target.value)}>
              <option value="">No change</option>
              <option value="not_submitted">not_submitted</option>
              <option value="in_progress">in_progress</option>
              <option value="submitted">submitted</option>
            </select>
          </div>
          <div className="form-group">
            <label>Readiness %</label>
            <input
              type="number"
              min={0}
              max={100}
              value={readinessVal}
              onChange={(e) => setReadinessVal(e.target.value)}
              placeholder="No change"
            />
          </div>
          <button
            className="btn-primary"
            onClick={handleOverride}
            disabled={!selectedTeam}
          >
            Apply Override
          </button>
        </div>
        {result && !result.error && (
          <div className="result-success">
            ✅ Override applied to {result.name}
          </div>
        )}
        {result?.error && <div className="result-error">❌ {result.error}</div>}
      </div>
    </div>
  )
}

// ─── Broadcast Panel ─────────────────────────────────────

function BroadcastPanel({ onSent }) {
  const [message, setMessage] = useState('')
  const [channel, setChannel] = useState('in_app')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  async function handleBroadcast() {
    if (!message.trim()) return
    setLoading(true)
    try {
      const res = await broadcastMessage(message, channel)
      setResult(res)
      setMessage('')
      onSent()
    } catch (err) {
      setResult({ error: err.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <h3 className="section-title">📢 Broadcast to All Participants</h3>
      <div className="broadcast-form">
        <textarea
          className="broadcast-input"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type your broadcast message…"
          rows={3}
        />
        <div className="form-row">
          <select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="in_app">In-App</option>
            <option value="discord">Discord</option>
            <option value="all">All Channels</option>
          </select>
          <button
            className="btn-primary"
            onClick={handleBroadcast}
            disabled={loading || !message.trim()}
          >
            {loading ? 'Sending…' : 'Send Broadcast'}
          </button>
        </div>
        {result && !result.error && (
          <div className="result-success">
            ✅ Broadcast sent to {result.notifications_sent} recipients
          </div>
        )}
        {result?.error && <div className="result-error">❌ {result.error}</div>}
      </div>
    </div>
  )
}

// ─── Main Dashboard ──────────────────────────────────────

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('health')
  const [health, setHealth] = useState(null)
  const [escalations, setEscalations] = useState(null)
  const [approvalQueue, setApprovalQueue] = useState(null)
  const [agentActions, setAgentActions] = useState(null)
  const [wsEvents, setWsEvents] = useState([])
  const wsRef = useRef(null)

  const loadHealth = useCallback(async () => {
    try {
      const data = await fetchDashboardHealth()
      setHealth(data)
    } catch (err) {
      console.error('Failed to load health:', err)
    }
  }, [])

  const loadEscalations = useCallback(async () => {
    try {
      const data = await fetchEscalations('open')
      setEscalations(data)
    } catch (err) {
      console.error('Failed to load escalations:', err)
    }
  }, [])

  const loadApprovalQueue = useCallback(async () => {
    try {
      const data = await fetchApprovalQueue()
      setApprovalQueue(data)
    } catch (err) {
      console.error('Failed to load approval queue:', err)
    }
  }, [])

  const loadAgentActions = useCallback(async () => {
    try {
      const data = await fetchAgentActions(100)
      setAgentActions(data)
    } catch (err) {
      console.error('Failed to load agent actions:', err)
    }
  }, [])

  const refreshAll = useCallback(() => {
    loadHealth()
    loadEscalations()
    loadApprovalQueue()
    loadAgentActions()
  }, [loadHealth, loadEscalations, loadApprovalQueue, loadAgentActions])

  // Initial load + WebSocket
  useEffect(() => {
    refreshAll()

    // Connect WebSocket for live updates
    try {
      wsRef.current = createDashboardWS((event) => {
        setWsEvents((prev) => [event, ...prev].slice(0, 50))
        // Auto-refresh relevant panels on events
        if (['team_override', 'broadcast', 'escalation', 'allocation'].includes(event.type)) {
          refreshAll()
        }
      })
    } catch (e) {
      console.warn('WebSocket not available, using polling fallback')
    }

    // Poll every 30s as fallback
    const interval = setInterval(refreshAll, 30000)

    return () => {
      clearInterval(interval)
      if (wsRef.current?._cleanup) wsRef.current._cleanup()
    }
  }, [refreshAll])

  async function handleResolve(escalationId) {
    try {
      await resolveEscalation(escalationId, 'Resolved from dashboard')
      loadEscalations()
      loadHealth()
    } catch (err) {
      alert('Failed to resolve: ' + err.message)
    }
  }

  async function handleRunSweep() {
    try {
      await runSweep()
      refreshAll()
    } catch (err) {
      alert('Sweep failed: ' + err.message)
    }
  }

  const tabs = [
    { id: 'health', label: 'Health', icon: '📊', count: health?.total_teams },
    { id: 'escalations', label: 'Escalations', icon: '🚨', count: health?.open_escalations },
    { id: 'approval', label: 'Approvals', icon: '✋', count: approvalQueue?.total_pending },
    { id: 'explainability', label: 'Agent Log', icon: '🤖', count: agentActions?.length },
    { id: 'overrides', label: 'Overrides', icon: '🔧' },
    { id: 'broadcast', label: 'Broadcast', icon: '📢' },
  ]

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dash-header">
        <div className="dash-header-left">
          <h1>⚡ Pulse Dashboard</h1>
          <span className="dash-version">v{health ? '1.2.0' : '…'}</span>
        </div>
        <div className="dash-header-right">
          <button className="btn-sm btn-blue" onClick={refreshAll}>
            🔄 Refresh
          </button>
          <button className="btn-sm btn-blue" onClick={handleRunSweep}>
            🤖 Run Sweep
          </button>
          <button className="btn-sm btn-green" onClick={exportSubmissionsCSV}>
            📥 Export CSV
          </button>
          <button className="btn-sm btn-gray" onClick={() => { clearToken(); window.location.href = '/login' }}>
            Logout
          </button>
        </div>
      </header>

      {/* Tabs */}
      <TabPanel tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Live events ticker */}
      {wsEvents.length > 0 && (
        <div className="ws-ticker">
          <span className="ticker-label">📡 Live:</span>
          {wsEvents.slice(0, 3).map((ev, i) => (
            <span key={i} className="ticker-event">
              {ev.type}: {ev.message || ev.team_name || JSON.stringify(ev.data || {}).slice(0, 60)}
            </span>
          ))}
        </div>
      )}

      {/* Content */}
      <main className="dash-content">
        {activeTab === 'health' && <HealthPanel health={health} />}
        {activeTab === 'escalations' && (
          <EscalationPanel escalations={escalations} onResolve={handleResolve} />
        )}
        {activeTab === 'approval' && <ApprovalPanel queue={approvalQueue} />}
        {activeTab === 'explainability' && <ExplainabilityPanel actions={agentActions} />}
        {activeTab === 'overrides' && <OverridePanel health={health} onOverride={refreshAll} />}
        {activeTab === 'broadcast' && <BroadcastPanel onSent={refreshAll} />}
      </main>
    </div>
  )
}
