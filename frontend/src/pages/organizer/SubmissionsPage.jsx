import { useState, useEffect } from 'react';
import { fetchAllSubmissions, fetchAllTeams } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';

export default function SubmissionsPage() {
  const [submissions, setSubmissions] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.allSettled([fetchAllSubmissions(), fetchAllTeams()])
      .then(([s, t]) => {
        if (s.status === 'fulfilled') setSubmissions(s.value);
        if (t.status === 'fulfilled') setTeams(t.value);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const teamMap = Object.fromEntries(teams.map(t => [t.id, t.name]));

  if (loading) return <LoadingSpinner text="Loading submissions..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Submissions</h1>
          <p className="page-subtitle">{submissions.length} submissions</p>
        </div>
      </div>

      {submissions.length === 0 ? (
        <EmptyState icon="📋" title="No submissions yet" description="Submissions will appear when teams submit their projects." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Team</th>
                <th>Completeness</th>
                <th>Repo</th>
                <th>Demo</th>
                <th>Description</th>
                <th>Last Audited</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map(sub => (
                <tr key={sub.id}>
                  <td className="table-cell-primary">{teamMap[sub.team_id] || 'Unknown'}</td>
                  <td>
                    <div className="progress" style={{ minWidth: '120px' }}>
                      <div className="progress-bar">
                        <div
                          className={`progress-fill ${sub.completeness_pct >= 80 ? 'success' : sub.completeness_pct >= 50 ? 'warning' : 'error'}`}
                          style={{ width: `${sub.completeness_pct}%` }}
                        />
                      </div>
                      <span className="progress-text">{sub.completeness_pct}%</span>
                    </div>
                  </td>
                  <td>{sub.repo_url ? <a href={sub.repo_url} target="_blank" rel="noopener noreferrer" className="text-sm">Link →</a> : <span className="text-muted">—</span>}</td>
                  <td>{sub.demo_url ? <a href={sub.demo_url} target="_blank" rel="noopener noreferrer" className="text-sm">Link →</a> : <span className="text-muted">—</span>}</td>
                  <td><span className="truncate" style={{ maxWidth: '200px', display: 'inline-block' }}>{sub.description?.slice(0, 60) || '—'}</span></td>
                  <td className="text-xs text-muted">{sub.last_audited_at ? new Date(sub.last_audited_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
