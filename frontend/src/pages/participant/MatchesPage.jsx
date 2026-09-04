import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchMyTeam, fetchMatchSuggestions } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';

export default function ParticipantMatchesPage() {
  const [team, setTeam] = useState(null);
  const [suggestions, setSuggestions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetchMyTeam()
      .then(t => {
        setTeam(t);
        return fetchMatchSuggestions(t.id);
      })
      .then(setSuggestions)
      .catch(e => {
        // A 404 from /teams/mine simply means the user has no team yet.
        setError(/team/i.test(e.message || '') ? 'no_team' : e.message);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner text="Finding match suggestions..." />;
  if (error === 'no_team' || !team) {
    return (
      <EmptyState
        icon="👥"
        title="Join a team first"
        description="Match suggestions compare your team's skill gaps against other participants. Create or join a team to get started."
        action={<Link className="btn btn-primary" to="/participant/team">Go to My Team</Link>}
      />
    );
  }
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Match Suggestions</h1>
          <p className="page-subtitle">Find teammates and mentors that complement your skills</p>
        </div>
      </div>

      {/* Gap Analysis */}
      {suggestions?.gap_analysis && (
        <div className="card mb-6">
          <h3 className="card-title mb-4">Skill Gap Analysis</h3>
          <div className="grid-2">
            <div>
              <div className="text-sm text-muted mb-2">Your Team's Skills</div>
              <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
                {suggestions.gap_analysis.team_skills?.length > 0 ? (
                  suggestions.gap_analysis.team_skills.map(s => (
                    <span key={s} className="badge badge-success">{s}</span>
                  ))
                ) : (
                  <span className="text-sm text-muted">No skills recorded yet</span>
                )}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted mb-2">Missing Skills</div>
              <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
                {suggestions.gap_analysis.missing_skills?.length > 0 ? (
                  suggestions.gap_analysis.missing_skills.map(s => (
                    <span key={s} className="badge badge-error">{s}</span>
                  ))
                ) : (
                  <span className="badge badge-success">No gaps — team is complete!</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Candidates */}
      <div className="section">
        <div className="section-header">
          <span className="section-title">Suggested Candidates</span>
          <span className="text-sm text-muted">{suggestions?.total_candidates || 0} found</span>
        </div>

        {suggestions?.candidates?.length > 0 ? (
          <div className="flex flex-col gap-3">
            {suggestions.candidates.map((candidate, i) => (
              <div key={candidate.participant_id} className="match-card">
                <div className="match-score">
                  <div className="match-score-value">{(candidate.match_score * 100).toFixed(0)}%</div>
                  <div className="match-score-label">Match</div>
                </div>
                <div className="match-body">
                  <div className="flex items-center gap-2">
                    <div className="avatar avatar-sm">{candidate.name?.[0]?.toUpperCase()}</div>
                    <div>
                      <div className="font-semibold">{candidate.name}</div>
                      <div className="text-xs text-muted">{candidate.email}</div>
                    </div>
                  </div>

                  <div className="match-skills">
                    {candidate.matching_skills?.map(s => (
                      <span key={s} className="badge badge-success">✓ {s}</span>
                    ))}
                  </div>

                  {candidate.reasoning && (
                    <div className="match-reasoning">{candidate.reasoning}</div>
                  )}

                  {candidate.discord_handle && (
                    <div className="text-xs text-muted mt-1">Discord: {candidate.discord_handle}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="🎯"
            title="No candidates found"
            description={suggestions?.message || "No unassigned participants match your team's skill gaps."}
          />
        )}
      </div>
    </div>
  );
}
