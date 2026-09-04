import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fetchMyIssues, reportIssue } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';
import Modal from '../../components/ui/Modal';

export default function ParticipantIssuesPage() {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showReport, setShowReport] = useState(false);
  const [form, setForm] = useState({ description: '', category: 'general', severity: 0.5, is_blocking: false });
  const [submitting, setSubmitting] = useState(false);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    fetchMyIssues()
      .then(setIssues)
      .catch(e => setError(/team/i.test(e.message || '') ? 'no_team' : e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleReport = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await reportIssue(form);
      toast('Issue reported!', 'success');
      setShowReport(false);
      setForm({ description: '', category: 'general', severity: 0.5, is_blocking: false });
      load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner text="Loading issues..." />;
  if (error === 'no_team') {
    return (
      <EmptyState
        icon="👥"
        title="Join a team to report issues"
        description="Issues are tied to your team. Create or join a team first, then report blockers here."
        action={<Link className="btn btn-primary" to="/participant/team">Go to My Team</Link>}
      />
    );
  }
  if (error) return <ErrorState message={error} onRetry={load} />;

  const open = issues.filter(i => i.status !== 'resolved');
  const resolved = issues.filter(i => i.status === 'resolved');

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Issues</h1>
          <p className="page-subtitle">{open.length} open · {resolved.length} resolved</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setShowReport(true)}>
          + Report Issue
        </button>
      </div>

      {issues.length === 0 ? (
        <EmptyState icon="🎉" title="No issues reported" description="Your team is doing great! Report an issue if you encounter any problems." />
      ) : (
        <>
          {open.length > 0 && (
            <section className="section">
              <div className="section-header">
                <span className="section-title">Open Issues</span>
                <span className="badge badge-error">{open.length}</span>
              </div>
              <div className="issue-list">
                {open.map(issue => <IssueItem key={issue.id} issue={issue} />)}
              </div>
            </section>
          )}

          {resolved.length > 0 && (
            <section className="section">
              <div className="section-header">
                <span className="section-title">Resolved</span>
              </div>
              <div className="issue-list">
                {resolved.map(issue => <IssueItem key={issue.id} issue={issue} />)}
              </div>
            </section>
          )}
        </>
      )}

      <Modal
        open={showReport}
        onClose={() => setShowReport(false)}
        title="Report an Issue"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setShowReport(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleReport} disabled={submitting || !form.description.trim()}>
              {submitting ? <><span className="loading-spinner" /> Submitting...</> : 'Report Issue'}
            </button>
          </>
        }
      >
        <form onSubmit={handleReport}>
          <div className="form-group">
            <label className="form-label">Description *</label>
            <textarea
              className="form-input form-textarea"
              placeholder="Describe the issue you're experiencing..."
              value={form.description}
              onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
              rows={4}
              required
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Category</label>
              <select
                className="form-input form-select"
                value={form.category}
                onChange={(e) => setForm(f => ({ ...f, category: e.target.value }))}
              >
                <option value="general">General</option>
                <option value="technical">Technical</option>
                <option value="deployment">Deployment</option>
                <option value="resource">Resource</option>
                <option value="mentor">Mentor</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Severity: {form.severity.toFixed(1)}</label>
              <input
                className="form-input"
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={form.severity}
                onChange={(e) => setForm(f => ({ ...f, severity: parseFloat(e.target.value) }))}
              />
              <div className="flex justify-between text-xs text-muted">
                <span>Low</span>
                <span>Critical</span>
              </div>
            </div>
          </div>
          <div className="form-group">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_blocking}
                onChange={(e) => setForm(f => ({ ...f, is_blocking: e.target.checked }))}
              />
              <span className="text-sm">This issue is blocking my team's progress</span>
            </label>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function IssueItem({ issue }) {
  const sevColor = issue.severity > 0.7 ? 'high' : issue.severity > 0.3 ? 'medium' : 'low';
  const isOpen = issue.status !== 'resolved';

  return (
    <div className="issue-item" style={{ opacity: isOpen ? 1 : 0.6 }}>
      <div className={`issue-severity ${sevColor}`} />
      <div className="issue-body">
        <div className="issue-header">
          <span className={`badge badge-dot ${isOpen ? 'badge-warning' : 'badge-success'}`}>
            {issue.status}
          </span>
          <span className="badge badge-neutral">{issue.category}</span>
          {issue.is_blocking && <span className="badge badge-error">Blocking</span>}
          <span className="text-xs text-muted ml-auto">{new Date(issue.created_at).toLocaleString()}</span>
        </div>
        <p className="issue-desc">{issue.description}</p>
        <div className="issue-meta">
          <span className="tag">Severity: {issue.severity}</span>
          <span className="tag">Urgency: {(issue.urgency_score * 100).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
}
