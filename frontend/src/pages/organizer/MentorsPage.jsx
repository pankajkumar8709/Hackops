import { useState, useEffect } from 'react';
import { fetchAllMentors } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';

export default function MentorsPage() {
  const [mentors, setMentors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAllMentors()
      .then(setMentors)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner text="Loading mentors..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Mentors</h1>
          <p className="page-subtitle">{mentors.length} mentors in roster</p>
        </div>
      </div>

      {mentors.length === 0 ? (
        <EmptyState icon="🎓" title="No mentors yet" description="Mentors will appear here once added." />
      ) : (
        <div className="grid-stats">
          {mentors.map(mentor => (
            <div key={mentor.id} className="card">
              <div className="flex items-center gap-3 mb-3">
                <div className="avatar">{mentor.name?.[0]?.toUpperCase()}</div>
                <div>
                  <div className="font-medium">{mentor.name}</div>
                  <span className={`badge badge-dot ${
                    mentor.availability_status === 'available' ? 'badge-success' :
                    mentor.availability_status === 'busy' ? 'badge-warning' : 'badge-neutral'
                  }`}>
                    {mentor.availability_status}
                  </span>
                </div>
              </div>
              <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
                {(mentor.skills || []).map(s => (
                  <span key={s} className="tag">{s}</span>
                ))}
              </div>
              {mentor.discord_handle && (
                <div className="text-xs text-muted mt-2">Discord: {mentor.discord_handle}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
