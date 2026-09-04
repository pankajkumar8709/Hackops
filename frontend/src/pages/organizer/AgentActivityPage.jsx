import { useState, useEffect, useCallback } from 'react';
import { fetchAgentActions, fetchOrchestratorStatus, runSweep } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';
import Modal from '../../components/ui/Modal';

export default function AgentActivityPage() {
  const [actions, setActions] = useState([]);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('');
  const [showSweep, setShowSweep] = useState(false);
  const [sweeping, setSweeping] = useState(false);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    Promise.allSettled([fetchAgentActions(100), fetchOrchestratorStatus()])
      .then(([a, s]) => {
        if (a.status === 'fulfilled') setActions(a.value);
        if (s.status === 'fulfilled') setStatus(s.value);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSweep = async () => {
    setSweeping(true);
    try {
      const result = await Promise.race([
        runSweep(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 60000)),
      ]);
      toast(`Sweep complete: ${result?.total_runs || 0} runs (${result?.verified_runs || 0} verified)`, 'success');
      setShowSweep(false);
      load();
    } catch (err) {
      if (err.message === 'timeout') {
        toast('Sweep is running in the background. Refresh in a minute to see results.', 'info');
        setShowSweep(false);
      } else {
        toast(err.message || 'Sweep failed', 'error');
      }
    } finally {
      setSweeping(false);
    }
  };

  if (loading) return <LoadingSpinner text="Loading agent activity..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const filtered = filter
    ? actions.filter(a => a.action_type?.includes(filter))
    : actions;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Agent Activity</h1>
          <p className="page-subtitle">Explainability feed — every orchestrator action</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <select
            className="form-input form-select"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{ maxWidth: '200px' }}
          >
            <option value="">All Types</option>
            <option value="send_notification">Notifications</option>
            <option value="propose_mentor">Propose Mentor</option>
            <option value="allocate_resource">Allocate Resource</option>
            <option value="create_escalation">Escalations</option>
            <option value="verify_sweep">Sweep Verifies</option>
          </select>
          <button className="btn btn-primary btn-sm" onClick={() => setShowSweep(true)}>
            ▶ Run Sweep
          </button>
        </div>
      </div>

      {/* Status Bar */}
      {status && (
        <div className="card mb-6">
          <div className="flex items-center gap-4 flex-wrap">
            <span className="badge badge-success badge-dot">{status.status}</span>
            <span className="text-sm text-muted">Version {status.version}</span>
            <span className="text-sm text-muted">Total actions: {status.total_actions_logged}</span>
            <div className="flex gap-1">
              {(status.trigger_types || []).map(t => (
                <span key={t} className="badge badge-info">{t}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Actions Feed */}
      {filtered.length === 0 ? (
        <EmptyState icon="🤖" title="No agent actions yet" description="Run the orchestrator to see actions appear here." />
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map(action => (
            <div key={action.id} className="action-card">
              <div className="action-card-header">
                <div className="flex items-center gap-2">
                  <span className="action-card-type">{action.action_type}</span>
                  <span className={`badge ${
                    action.policy_check_result?.includes('ALLOWED') ? 'badge-success' :
                    action.policy_check_result?.includes('RESTRICTED') || action.policy_check_result?.includes('BLOCKED') ? 'badge-error' :
                    'badge-warning'
                  }`}>
                    {action.policy_check_result?.slice(0, 18) || 'N/A'}
                  </span>
                </div>
                <span className="text-xs text-muted">{new Date(action.executed_at).toLocaleString()}</span>
              </div>

              {/* Plain-language summary first — never a raw JSON dump */}
              {action.summary && (
                <div className="action-card-summary">{action.summary}</div>
              )}

              {action.trigger_state_snapshot && (
                <details className="action-card-details">
                  <summary className="text-xs text-muted">Trigger state (raw)</summary>
                  <pre style={{ fontSize: '11px', overflowX: 'auto' }}>
                    {action.trigger_state_snapshot.slice(0, 500)}
                  </pre>
                </details>
              )}

              {action.reasoning_trace && (
                <div className="action-card-reasoning">
                  {action.reasoning_trace.slice(0, 300)}
                </div>
              )}

              <div className="action-card-footer">
                <span className={`badge ${
                  action.outcome?.includes('success') ? 'badge-success' :
                  action.outcome?.includes('error') ? 'badge-error' :
                  'badge-neutral'
                }`}>
                  {action.outcome?.slice(0, 30) || 'completed'}
                </span>
                <div className="flex gap-1">
                  {action.issue_id && <span className="tag">issue</span>}
                  {action.notification_id && <span className="tag">notification</span>}
                  {action.submission_id && <span className="tag">submission</span>}
                  {action.escalation_id && <span className="tag">escalation</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={showSweep}
        onClose={() => setShowSweep(false)}
        title="Run orchestrator sweep?"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowSweep(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleSweep} disabled={sweeping}>
              {sweeping ? <><span className="loading-spinner" /> Running...</> : 'Run Sweep'}
            </button>
          </>
        }
      >
        <div className="text-sm">
          <p>The agent will audit every team and open issue, and check out-of-stock resource pools.</p>
          <p className="mt-2" style={{ color: 'var(--text-secondary)' }}>
            Concretely this can:
          </p>
          <ul className="mt-1" style={{ paddingLeft: '20px', color: 'var(--text-secondary)' }}>
            <li>Send reminder notifications to teams below 100% readiness</li>
            <li>Propose mentor allocations for unassigned open issues</li>
            <li>Notify teams whose requested resource pool is out of stock</li>
            <li>Log every decision to the explainability feed</li>
          </ul>
        </div>
      </Modal>
    </div>
  );
}
