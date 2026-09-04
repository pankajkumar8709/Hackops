import { useState, useEffect } from 'react';
import { fetchAllTeams } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';

export default function TeamsPage() {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAllTeams()
      .then(setTeams)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner text="Loading teams..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Teams</h1>
          <p className="page-subtitle">{teams.length} teams registered</p>
        </div>
      </div>

      {teams.length === 0 ? (
        <EmptyState icon="👥" title="No teams yet" description="Teams will appear when participants register." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Team</th>
                <th>Status</th>
                <th>Readiness</th>
                <th>Track</th>
              </tr>
            </thead>
            <tbody>
              {teams.map(team => (
                <tr key={team.id}>
                  <td className="table-cell-primary">{team.name}</td>
                  <td>
                    <span className={`badge badge-dot ${
                      team.submission_status === 'submitted' ? 'badge-success' :
                      team.submission_status === 'in_progress' ? 'badge-warning' : 'badge-neutral'
                    }`}>
                      {team.submission_status?.replace('_', ' ')}
                    </span>
                  </td>
                  <td>
                    <div className="progress" style={{ minWidth: '120px' }}>
                      <div className="progress-bar">
                        <div
                          className={`progress-fill ${team.readiness_pct >= 100 ? 'success' : team.readiness_pct >= 50 ? 'warning' : 'error'}`}
                          style={{ width: `${Math.min(team.readiness_pct, 100)}%` }}
                        />
                      </div>
                      <span className="progress-text">{team.readiness_pct}%</span>
                    </div>
                  </td>
                  <td>{team.track_id ? <span className="badge badge-info">Has Track</span> : <span className="badge badge-neutral">No Track</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
