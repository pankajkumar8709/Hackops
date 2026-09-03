import { useState, useEffect } from 'react'
import {
  fetchMyTeam,
  fetchMySubmission,
  fetchMyIssues,
  fetchMyResourceAllocations,
  fetchMyNotifications,
  markNotificationRead,
} from '../api'

export default function ParticipantTeamPage() {
  const [team, setTeam] = useState(null)
  const [submission, setSubmission] = useState(null)
  const [issues, setIssues] = useState([])
  const [resources, setResources] = useState([])
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const teamData = await fetchMyTeam()
      setTeam(teamData)

      // Load all in parallel
      const [sub, iss, res, notifs] = await Promise.allSettled([
        fetchMySubmission(),
        fetchMyIssues(),
        fetchMyResourceAllocations(),
        fetchMyNotifications(),
      ])
      if (sub.status === 'fulfilled') setSubmission(sub.value)
      if (iss.status === 'fulfilled') setIssues(iss.value)
      if (res.status === 'fulfilled') setResources(res.value)
      if (notifs.status === 'fulfilled') setNotifications(notifs.value)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleMarkRead(notifId) {
    try {
      await markNotificationRead(notifId)
      setNotifications((prev) =>
        prev.map((n) => n.id === notifId ? { ...n, read: true } : n)
      )
    } catch (err) {
      console.error('Failed to mark read:', err)
    }
  }

  if (loading) return <div className="p-loading">Loading team status…</div>
  if (error) return <div className="p-error">Error: {error}</div>

  const unreadCount = notifications.filter((n) => !n.read).length
  const activeAllocations = resources.filter((r) => r.status === 'allocated')
  const openIssues = issues.filter((i) => i.status !== 'resolved')

  return (
    <div className="p-page">
      <h2 className="p-page-title">🏠 Team Status</h2>

      {/* Team Info */}
      {team && (
        <div className="p-card">
          <div className="p-card-header">
            <h3>{team.name}</h3>
            <span className={`p-badge ${team.submission_status === 'submitted' ? 'green' : 'gray'}`}>
              {team.submission_status}
            </span>
          </div>
          <div className="p-readiness">
            <span className="p-readiness-label">Readiness</span>
            <div className="p-progress-bar">
              <div
                className="p-progress-fill"
                style={{
                  width: `${team.readiness_pct}%`,
                  backgroundColor: team.readiness_pct >= 100 ? '#10b981' : team.readiness_pct > 50 ? '#f59e0b' : '#ef4444',
                }}
              />
            </div>
            <span className="p-readiness-pct">{team.readiness_pct}%</span>
          </div>
        </div>
      )}

      {/* Submission */}
      <div className="p-card">
        <h3 className="p-card-title">📦 Submission</h3>
        {submission ? (
          <div className="p-details">
            <div className="p-detail-row">
              <span>Repo URL</span>
              <a href={submission.repo_url} target="_blank" rel="noopener noreferrer">
                {submission.repo_url || '—'}
              </a>
            </div>
            <div className="p-detail-row">
              <span>Demo URL</span>
              <a href={submission.demo_url} target="_blank" rel="noopener noreferrer">
                {submission.demo_url || '—'}
              </a>
            </div>
            <div className="p-detail-row">
              <span>Description</span>
              <span>{submission.description || '—'}</span>
            </div>
            <div className="p-detail-row">
              <span>Completeness</span>
              <span className="p-highlight">{submission.completeness_pct}%</span>
            </div>
          </div>
        ) : (
          <div className="p-empty">No submission yet. Create one from your team settings.</div>
        )}
      </div>

      {/* Issues */}
      <div className="p-card">
        <h3 className="p-card-title">
          🚨 Issues ({openIssues.length} open / {issues.length} total)
        </h3>
        {issues.length === 0 ? (
          <div className="p-empty">No issues reported yet. 🎉</div>
        ) : (
          <div className="p-list">
            {issues.map((issue) => (
              <div key={issue.id} className={`p-list-item p-border-${issue.status === 'resolved' ? 'green' : 'red'}`}>
                <div className="p-list-header">
                  <span className={`p-badge ${issue.status === 'resolved' ? 'green' : 'yellow'}`}>
                    {issue.status}
                  </span>
                  <span className="p-list-meta">Severity: {issue.severity}</span>
                  {issue.is_blocking && <span className="p-badge red">BLOCKING</span>}
                </div>
                <p className="p-list-text">{issue.description}</p>
                <span className="p-list-time">{new Date(issue.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Resource Allocations */}
      <div className="p-card">
        <h3 className="p-card-title">
          📦 Resources ({activeAllocations.length} active)
        </h3>
        {resources.length === 0 ? (
          <div className="p-empty">No resources allocated yet.</div>
        ) : (
          <div className="p-list">
            {resources.map((res) => (
              <div key={res.id} className={`p-list-item p-border-${res.status === 'allocated' ? 'blue' : res.status === 'overdue' ? 'red' : 'green'}`}>
                <div className="p-list-header">
                  <span className={`p-badge ${res.status === 'allocated' ? 'blue' : res.status === 'overdue' ? 'red' : 'green'}`}>
                    {res.status}
                  </span>
                  <span className="p-list-meta">{res.resource_item?.name || 'Resource'}</span>
                </div>
                <p className="p-list-text">Type: {res.resource_item?.resource_type || '—'}</p>
                <span className="p-list-time">Allocated: {new Date(res.allocated_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Notifications */}
      <div className="p-card">
        <h3 className="p-card-title">
          🔔 Notifications ({unreadCount} unread)
        </h3>
        {notifications.length === 0 ? (
          <div className="p-empty">No notifications yet.</div>
        ) : (
          <div className="p-list">
            {notifications.map((notif) => (
              <div
                key={notif.id}
                className={`p-list-item p-notif ${notif.read ? 'read' : 'unread'}`}
                onClick={() => !notif.read && handleMarkRead(notif.id)}
              >
                <div className="p-list-header">
                  <span className={`p-badge ${notif.read ? 'gray' : 'blue'}`}>
                    {notif.read ? 'Read' : 'New'}
                  </span>
                  {notif.reminder_type && (
                    <span className="p-list-meta">{notif.reminder_type}</span>
                  )}
                </div>
                <p className="p-list-text">{notif.content}</p>
                <span className="p-list-time">{new Date(notif.sent_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
