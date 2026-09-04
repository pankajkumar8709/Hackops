import { useState, useEffect, useCallback } from 'react';
import { fetchEscalations, resolveEscalation } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';
import Modal from '../../components/ui/Modal';

export default function EscalationsPage() {
  const [escalations, setEscalations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [resolveModal, setResolveModal] = useState(null);
  const [resolution, setResolution] = useState('');
  const [assignee, setAssignee] = useState('');
  const [resolving, setResolving] = useState(false);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    fetchEscalations()
      .then(setEscalations)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleResolve = async () => {
    setResolving(true);
    try {
      await resolveEscalation(resolveModal.id, resolution, assignee);
      toast('Escalation resolved!', 'success');
      setResolveModal(null);
      setResolution('');
      setAssignee('');
      load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setResolving(false);
    }
  };

  if (loading) return <LoadingSpinner text="Loading escalations..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const open = escalations.filter(e => e.status !== 'resolved');
  const resolved = escalations.filter(e => e.status === 'resolved');

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Escalations</h1>
          <p className="page-subtitle">{open.length} open · {resolved.length} resolved</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load}>↻ Refresh</button>
      </div>

      {escalations.length === 0 ? (
        <EmptyState icon="🎉" title="No escalations" description="All issues are resolved or none have been created." />
      ) : (
        <>
          {open.length > 0 && (
            <section className="section">
              <div className="section-header">
                <span className="section-title">Open</span>
                <span className="badge badge-error">{open.length}</span>
              </div>
              <div className="feed-list">
                {open.map(esc => (
                  <EscalationItem key={esc.id} escalation={esc} onResolve={() => setResolveModal(esc)} />
                ))}
              </div>
            </section>
          )}

          {resolved.length > 0 && (
            <section className="section">
              <div className="section-header">
                <span className="section-title">Resolved</span>
              </div>
              <div className="feed-list">
                {resolved.map(esc => (
                  <EscalationItem key={esc.id} escalation={esc} />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <Modal
        open={!!resolveModal}
        onClose={() => { setResolveModal(null); setResolution(''); setAssignee(''); }}
        title="Resolve Escalation"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => { setResolveModal(null); setResolution(''); }}>Cancel</button>
            <button className="btn btn-success" onClick={handleResolve} disabled={resolving}>
              {resolving ? <><span className="loading-spinner" /> Resolving...</> : 'Mark Resolved'}
            </button>
          </>
        }
      >
        {resolveModal?.issue && (
          <div className="mb-4">
            <div className="text-sm text-muted mb-2">Issue Description</div>
            <div className="text-sm">{resolveModal.issue.description}</div>
            <div className="flex gap-2 mt-2">
              <span className="badge badge-error">Urgency: {(resolveModal.urgency_score * 100).toFixed(0)}%</span>
              <span className="badge badge-neutral">{resolveModal.issue.category}</span>
              <span className="badge badge-neutral">Severity: {resolveModal.issue.severity}</span>
            </div>
          </div>
        )}
        <div className="form-group">
          <label className="form-label">Assigned To (optional)</label>
          <input
            className="form-input"
            placeholder="Mentor or organizer who handled this"
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">Resolution Notes (optional)</label>
          <textarea
            className="form-input form-textarea"
            placeholder="How was this resolved?"
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
          />
        </div>
        <p className="text-xs text-muted">
          Resolving closes this escalation and marks the underlying issue as resolved.
        </p>
      </Modal>
    </div>
  );
}

function EscalationItem({ escalation: esc, onResolve }) {
  const urgency = (esc.urgency_score * 100).toFixed(0);
  const isResolved = esc.status === 'resolved';

  return (
    <div className="escalation-item" style={{ opacity: isResolved ? 0.6 : 1, borderLeftColor: isResolved ? 'var(--success)' : 'var(--error)' }}>
      <div className="escalation-urgency">
        <span className="escalation-urgency-value" style={{ color: isResolved ? 'var(--success)' : esc.urgency_score > 0.7 ? 'var(--error)' : 'var(--warning)' }}>
          {urgency}%
        </span>
        <span className="escalation-urgency-label">Urgency</span>
      </div>
      <div className="escalation-body">
        <div className="flex items-center gap-2 mb-2">
          <span className={`badge badge-dot ${isResolved ? 'badge-success' : 'badge-error'}`}>
            {esc.status}
          </span>
          <span className="badge badge-neutral">{esc.issue?.category}</span>
          <span className="text-xs text-muted">{new Date(esc.created_at).toLocaleString()}</span>
        </div>
        {esc.issue && (
          <p className="text-sm" style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>
            {esc.issue.description?.slice(0, 200)}
          </p>
        )}
        {esc.assigned_organizer && (
          <div className="text-xs text-muted mb-1">Assigned to: <strong>{esc.assigned_organizer}</strong></div>
        )}
        {esc.resolution_notes && (
          <div className="text-xs text-muted" style={{ fontStyle: 'italic' }}>
            Resolution: {esc.resolution_notes}
          </div>
        )}
        {!isResolved && onResolve && (
          <button className="btn btn-success btn-sm mt-2" onClick={onResolve}>
            ✓ Resolve
          </button>
        )}
      </div>
    </div>
  );
}
