import { useState, useEffect } from 'react';
import { fetchMySubmission, createOrUpdateSubmission, fetchSubmissionAudit } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';

export default function ParticipantSubmissionPage() {
  const [submission, setSubmission] = useState(null);
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ repo_url: '', readme_url: '', demo_url: '', description: '' });
  const toast = useToast();

  useEffect(() => {
    setLoading(true);
    fetchMySubmission()
      .then(sub => {
        setSubmission(sub);
        setForm({
          repo_url: sub.repo_url || '',
          readme_url: sub.readme_url || '',
          demo_url: sub.demo_url || '',
          description: sub.description || '',
        });
        return fetchSubmissionAudit(sub.id);
      })
      .then(a => setAudit(a))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const sub = await createOrUpdateSubmission(form);
      setSubmission(sub);
      const a = await fetchSubmissionAudit(sub.id);
      setAudit(a);
      toast('Submission saved!', 'success');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner text="Loading submission..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Submission</h1>
          <p className="page-subtitle">Submit your hackathon project</p>
        </div>
      </div>

      <div className="grid-2">
        {/* Submission Form */}
        <div className="card">
          <h3 className="card-title mb-4">{submission ? 'Update Submission' : 'New Submission'}</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Repository URL *</label>
              <input
                className="form-input"
                type="url"
                placeholder="https://github.com/..."
                value={form.repo_url}
                onChange={(e) => setForm(f => ({ ...f, repo_url: e.target.value }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">README URL</label>
              <input
                className="form-input"
                type="url"
                placeholder="https://github.com/.../README.md"
                value={form.readme_url}
                onChange={(e) => setForm(f => ({ ...f, readme_url: e.target.value }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Demo URL</label>
              <input
                className="form-input"
                type="url"
                placeholder="https://your-demo.vercel.app"
                value={form.demo_url}
                onChange={(e) => setForm(f => ({ ...f, demo_url: e.target.value }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea
                className="form-input form-textarea"
                placeholder="Describe your project..."
                value={form.description}
                onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
                rows={4}
              />
            </div>
            <button type="submit" className="btn btn-primary btn-full" disabled={saving}>
              {saving ? <><span className="loading-spinner" /> Saving...</> : submission ? 'Update Submission' : 'Submit Project'}
            </button>
          </form>

          {submission && (
            <div className="text-xs text-muted mt-4">
              Last updated: {new Date(submission.updated_at).toLocaleString()}
            </div>
          )}
        </div>

        {/* Audit Results */}
        <div className="card">
          <h3 className="card-title mb-4">Audit Results</h3>
          {audit ? (
            <>
              <div style={{ textAlign: 'center', padding: '16px 0', marginBottom: '16px' }}>
                <div style={{ fontSize: '36px', fontWeight: 'bold', color: audit.completeness_pct >= 80 ? 'var(--success)' : 'var(--warning)' }}>
                  {audit.completeness_pct}%
                </div>
                <div className="text-sm text-muted">Completeness</div>
              </div>

              <div className="progress mb-4">
                <div className="progress-bar" style={{ height: '8px' }}>
                  <div
                    className={`progress-fill ${audit.completeness_pct >= 80 ? 'success' : audit.completeness_pct >= 50 ? 'warning' : 'error'}`}
                    style={{ width: `${audit.completeness_pct}%` }}
                  />
                </div>
              </div>

              <div className="checklist">
                {audit.fields?.map(field => (
                  <div key={field.field_name} className={`checklist-item ${field.passed ? 'pass' : 'fail'}`}>
                    <div className="checklist-icon">{field.passed ? '✓' : '✕'}</div>
                    <span>{field.field_name}</span>
                    {field.required && <span className="badge badge-neutral" style={{ marginLeft: 'auto' }}>Required</span>}
                  </div>
                ))}
              </div>

              <div className="text-xs text-muted mt-4">
                {audit.total_present}/{audit.total_required} required fields present
              </div>
            </>
          ) : (
            <EmptyState icon="📋" title="No audit yet" description="Submit your project to run an audit." />
          )}
        </div>
      </div>
    </div>
  );
}
