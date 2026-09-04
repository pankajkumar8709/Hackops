import { useState, useEffect, useCallback } from 'react';
import { fetchAllNotifications, broadcastMessage, sendNotification, fetchAllParticipants } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('all');
  const [broadcastMsg, setBroadcastMsg] = useState('');
  const [broadcastLoading, setBroadcastLoading] = useState(false);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    Promise.allSettled([fetchAllNotifications(50), fetchAllParticipants()])
      .then(([n, p]) => {
        if (n.status === 'fulfilled') setNotifications(n.value);
        if (p.status === 'fulfilled') setParticipants(p.value);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleBroadcast = async () => {
    if (!broadcastMsg.trim()) return;
    setBroadcastLoading(true);
    try {
      await broadcastMessage(broadcastMsg);
      toast(`Broadcast sent to ${participants.length} participants!`, 'success');
      setBroadcastMsg('');
      load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setBroadcastLoading(false);
    }
  };

  if (loading) return <LoadingSpinner text="Loading notifications..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">{notifications.length} notifications</p>
        </div>
      </div>

      <div className="tabs mb-6">
        <button className={`tab ${tab === 'all' ? 'active' : ''}`} onClick={() => setTab('all')}>All Notifications</button>
        <button className={`tab ${tab === 'broadcast' ? 'active' : ''}`} onClick={() => setTab('broadcast')}>Broadcast</button>
      </div>

      {tab === 'broadcast' && (
        <div className="card mb-6">
          <h3 className="card-title mb-4">Broadcast Message</h3>
          <div className="form-group">
            <textarea
              className="form-input form-textarea"
              placeholder="Type a message to broadcast to all participants..."
              value={broadcastMsg}
              onChange={(e) => setBroadcastMsg(e.target.value)}
              rows={3}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted">{participants.length} recipients</span>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleBroadcast}
              disabled={broadcastLoading || !broadcastMsg.trim()}
            >
              {broadcastLoading ? <><span className="loading-spinner" /> Sending...</> : '📢 Send Broadcast'}
            </button>
          </div>
        </div>
      )}

      {tab === 'all' && (
        notifications.length === 0 ? (
          <EmptyState icon="🔔" title="No notifications" description="Notifications will appear here." />
        ) : (
          <div className="notification-list">
            {notifications.map(n => (
              <div key={n.id} className={`notification-item ${n.read ? 'read' : 'unread'}`}>
                <div className="avatar avatar-sm">🔔</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="text-sm">{n.content}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="badge badge-neutral">{n.reminder_type || 'general'}</span>
                    <span className="badge badge-neutral">{n.channel}</span>
                    <span className="text-xs text-muted">{new Date(n.sent_at).toLocaleString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}
