import { useState, useEffect } from 'react';
import { fetchAllParticipants } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';

export default function ParticipantsPage() {
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchAllParticipants()
      .then(setParticipants)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = participants.filter(p =>
    p.name?.toLowerCase().includes(search.toLowerCase()) ||
    p.email?.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <LoadingSpinner text="Loading participants..." />;
  if (error) return <ErrorState message={error} onRetry={() => { setLoading(true); setError(null); fetchAllParticipants().then(setParticipants).catch(e => setError(e.message)).finally(() => setLoading(false)); }} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Participants</h1>
          <p className="page-subtitle">{participants.length} registered participants</p>
        </div>
        <input
          className="form-input"
          placeholder="Search participants..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: '280px' }}
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon="👤" title="No participants found" description={search ? 'Try a different search.' : 'No participants have registered yet.'} />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Skills</th>
                <th>Track</th>
                <th>Discord</th>
                <th>Team</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => (
                <tr key={p.id}>
                  <td className="table-cell-primary">
                    <div className="flex items-center gap-2">
                      <div className="avatar avatar-sm">{p.name?.[0]?.toUpperCase()}</div>
                      {p.name}
                    </div>
                  </td>
                  <td>{p.email}</td>
                  <td>
                    <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
                      {(p.skills || []).slice(0, 3).map(s => (
                        <span key={s} className="tag">{s}</span>
                      ))}
                      {(p.skills || []).length > 3 && (
                        <span className="tag">+{p.skills.length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td>{p.track_pref || '—'}</td>
                  <td>{p.discord_handle || '—'}</td>
                  <td>
                    {p.team_id ? (
                      <span className="badge badge-primary">In Team</span>
                    ) : (
                      <span className="badge badge-neutral">No Team</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
