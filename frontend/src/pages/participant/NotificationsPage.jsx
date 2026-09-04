import { useState, useEffect, useCallback } from 'react';
import { fetchMyNotifications, markNotificationRead } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';

export default function ParticipantNotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    fetchMyNotifications()
      .then(setNotifications)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleMarkRead = async (id) => {
    try {
      await markNotificationRead(id);
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, read: true } : n)
      );
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  if (loading) return <LoadingSpinner text="Loading notifications..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const unread = notifications.filter(n => !n.read);
  const read = notifications.filter(n => n.read);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">{unread.length} unread · {read.length} read</p>
        </div>
      </div>

      {notifications.length === 0 ? (
        <EmptyState icon="🔔" title="No notifications" description="You'll receive notifications about your team's progress and deadlines." />
      ) : (
        <>
          {unread.length > 0 && (
            <section className="section">
              <div className="section-header">
                <span className="section-title">Unread</span>
                <span className="badge badge-primary">{unread.length}</span>
              </div>
              <div className="notification-list">
                {unread.map(n => (
                  <NotificationItem key={n.id} notification={n} onMarkRead={handleMarkRead} />
                ))}
              </div>
            </section>
          )}

          {read.length > 0 && (
            <section className="section">
              <div className="section-header">
                <span className="section-title">Read</span>
              </div>
              <div className="notification-list">
                {read.map(n => (
                  <NotificationItem key={n.id} notification={n} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function NotificationItem({ notification: n, onMarkRead }) {
  const typeIcons = {
    deadline_reminder: '⏰',
    submission_reminder: '📋',
    broadcast: '📢',
    mentor_assignment: '🎓',
    resource_alert: '📦',
    general: '🔔',
  };

  return (
    <div className={`notification-item ${n.read ? 'read' : 'unread'}`} onClick={() => !n.read && onMarkRead?.(n.id)}>
      <div className="avatar avatar-sm" style={{ background: n.read ? 'var(--bg-elevated)' : 'var(--primary-muted)' }}>
        {typeIcons[n.reminder_type] || '🔔'}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="text-sm">{n.content}</div>
        <div className="flex items-center gap-2 mt-1">
          <span className="badge badge-neutral">{n.reminder_type?.replace('_', ' ') || 'general'}</span>
          <span className="badge badge-neutral">{n.channel}</span>
          <span className="text-xs text-muted">{new Date(n.sent_at).toLocaleString()}</span>
        </div>
      </div>
      {!n.read && (
        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--primary)', flexShrink: 0 }} />
      )}
    </div>
  );
}
