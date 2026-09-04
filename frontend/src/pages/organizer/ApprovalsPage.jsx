import { useState, useEffect, useCallback } from 'react';
import { fetchApprovalQueue, approveApprovalItem, rejectApprovalItem } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';
import Modal from '../../components/ui/Modal';

export default function ApprovalsPage() {
  const [queue, setQueue] = useState({ items: [], total_pending: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [acting, setActing] = useState(null); // item being decided
  const [decision, setDecision] = useState(null); // 'approve' | 'reject'
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    fetchApprovalQueue()
      .then(setQueue)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const openConfirm = (item, decision) => {
    setActing(item);
    setDecision(decision);
  };

  const runDecision = async () => {
    if (!acting) return;
    try {
      if (decision === 'approve') {
        await approveApprovalItem(acting.id);
        toast('Approved — action executed.', 'success');
      } else {
        await rejectApprovalItem(acting.id);
        toast('Rejected — action discarded.', 'info');
      }
      setActing(null);
      setDecision(null);
      load();
    } catch (err) {
      toast(err.message || 'Action failed', 'error');
      setActing(null);
      setDecision(null);
    }
  };

  if (loading) return <LoadingSpinner text="Loading approval queue..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const effect =
    acting?.action_type === 'propose_mentor'
      ? decision === 'approve'
        ? 'The mentor will be assigned to the issue and the team notified.'
        : 'The mentor proposal will be declined. The agent may propose a different mentor on its next sweep.'
      : decision === 'approve'
        ? 'Restock will be authorized and logged to the agent audit trail.'
        : 'The out-of-stock alert will be dismissed and logged to the agent audit trail.';

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Approvals</h1>
          <p className="page-subtitle">Agent-proposed actions requiring human review</p>
        </div>
        <span className="badge badge-warning">{queue.total_pending} pending</span>
      </div>

      {queue.items.length === 0 ? (
        <EmptyState icon="✅" title="Approval queue is clear" description="No pending approvals." />
      ) : (
        <div className="feed-list">
          {queue.items.map(item => (
            <div key={item.id} className="feed-item" style={{ borderLeftColor: 'var(--warning)' }}>
              <div className="feed-item-icon" style={{ background: 'var(--warning-muted)', color: 'var(--warning)' }}>
                {item.action_type === 'propose_mentor' ? '🎓' : '📦'}
              </div>
              <div className="feed-item-body">
                <div className="feed-item-header">
                  <span className="feed-item-title">{item.action_type.replace(/_/g, ' ')}</span>
                  <span className="feed-item-time">{new Date(item.created_at).toLocaleString()}</span>
                </div>
                <div className="feed-item-desc">{item.description}</div>
                {item.reasoning && (
                  <div className="text-xs text-muted mt-2" style={{ fontFamily: 'var(--font-mono)' }}>
                    {item.reasoning.slice(0, 200)}
                  </div>
                )}
                <div className="feed-item-meta mt-2">
                  <span className="badge badge-warning">{item.status}</span>
                  <span className="badge badge-neutral">{item.entity_type}</span>
                </div>
                <div className="flex gap-2 mt-3">
                  <button className="btn btn-success btn-sm" onClick={() => openConfirm(item, 'approve')}>
                    ✓ Approve
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={() => openConfirm(item, 'reject')}>
                    ✕ Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={!!acting}
        onClose={() => { setActing(null); setDecision(null); }}
        title={decision === 'approve' ? 'Approve this action?' : 'Reject this action?'}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => { setActing(null); setDecision(null); }}>
              Cancel
            </button>
            <button
              className={`btn ${decision === 'approve' ? 'btn-success' : 'btn-secondary'}`}
              onClick={runDecision}
            >
              {decision === 'approve' ? '✓ Approve' : '✕ Reject'}
            </button>
          </>
        }
      >
        <div className="text-sm">
          <p><strong>{acting?.action_type?.replace(/_/g, ' ')}</strong> — {acting?.description}</p>
          <p className="mt-2" style={{ color: 'var(--text-secondary)' }}>{effect}</p>
        </div>
      </Modal>
    </div>
  );
}
