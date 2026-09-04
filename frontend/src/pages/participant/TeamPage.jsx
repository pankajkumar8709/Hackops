import { useState, useEffect } from 'react';
import { fetchMyTeam, fetchMyProfile, createTeam, joinTeam } from '../../api';
import { LoadingSpinner, ErrorState, EmptyState } from '../../components/ui/States';
import { useToast } from '../../components/ui/Toast';

export default function ParticipantTeamPage() {
  const [team, setTeam] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState('choose'); // choose | create | join
  const [teamName, setTeamName] = useState('');
  const [joinId, setJoinId] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = () => {
    setLoading(true);
    Promise.allSettled([fetchMyTeam(), fetchMyProfile()])
      .then(([t, p]) => {
        if (t.status === 'fulfilled') setTeam(t.value);
        if (p.status === 'fulfilled') setProfile(p.value);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await createTeam(teamName.trim());
      toast('Team created!', 'success');
      load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const handleJoin = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await joinTeam(joinId.trim());
      toast('Joined team!', 'success');
      load();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <LoadingSpinner text="Loading team..." />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  if (!team) {
    return (
      <div>
        <div className="page-header">
          <div>
            <h1 className="page-title">My Team</h1>
            <p className="page-subtitle">You aren't in a team yet</p>
          </div>
        </div>
        <div className="card" style={{ maxWidth: '560px' }}>
          <h3 className="card-title mb-3">Join the hackathon as a team</h3>
          <p className="text-sm text-muted mb-4">
            Create your own team and invite your friends, or join an existing team with the
            ID your organizer shared.
          </p>

          {mode === 'create' ? (
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label className="form-label" htmlFor="teamName">Team Name</label>
                <input
                  id="teamName"
                  className="form-input"
                  placeholder="Team Alpha"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  autoFocus
                />
                <span className="form-hint">A track will be assigned by the organizer.</span>
              </div>
              <div className="flex gap-2">
                <button className="btn btn-primary" disabled={busy || !teamName.trim()}>
                  {busy ? <><span className="loading-spinner" /> Creating...</> : 'Create Team'}
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => setMode('choose')}>
                  Back
                </button>
              </div>
            </form>
          ) : mode === 'join' ? (
            <form onSubmit={handleJoin}>
              <div className="form-group">
                <label className="form-label" htmlFor="joinId">Team ID</label>
                <input
                  id="joinId"
                  className="form-input"
                  placeholder="Paste the team ID from your organizer"
                  value={joinId}
                  onChange={(e) => setJoinId(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="flex gap-2">
                <button className="btn btn-primary" disabled={busy || !joinId.trim()}>
                  {busy ? <><span className="loading-spinner" /> Joining...</> : 'Join Team'}
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => setMode('choose')}>
                  Back
                </button>
              </div>
            </form>
          ) : (
            <div className="grid-2">
              <button className="btn btn-primary btn-lg" onClick={() => setMode('create')}>
                🚀 Create a Team
              </button>
              <button className="btn btn-secondary btn-lg" onClick={() => setMode('join')}>
                🎟️ Join an Existing Team
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{team.name}</h1>
          <p className="page-subtitle">Your team overview</p>
        </div>
      </div>

      <div className="team-overview">
        <div className="card">
          <h3 className="card-title mb-4">Team Info</h3>
          <div className="team-info-grid">
            <div className="team-info-row">
              <span className="team-info-label">Status</span>
              <span className="team-info-value">
                <span className={`badge badge-dot ${
                  team.submission_status === 'submitted' ? 'badge-success' :
                  team.submission_status === 'in_progress' ? 'badge-warning' : 'badge-neutral'
                }`}>
                  {team.submission_status?.replace('_', ' ')}
                </span>
              </span>
            </div>
            <div className="team-info-row">
              <span className="team-info-label">Track</span>
              <span className="team-info-value">{team.track_id ? 'Assigned' : 'No track'}</span>
            </div>
            <div className="team-info-row">
              <span className="team-info-label">Team ID</span>
              <span className="team-info-value text-xs text-muted">{team.id?.slice(0, 8)}...</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 className="card-title mb-4">Readiness</h3>
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ fontSize: '48px', fontWeight: 'bold', color: team.readiness_pct >= 100 ? 'var(--success)' : 'var(--warning)' }}>
              {team.readiness_pct}%
            </div>
            <div className="text-sm text-muted mb-4">Overall Readiness</div>
            <div className="progress" style={{ maxWidth: '300px', margin: '0 auto' }}>
              <div className="progress-bar" style={{ height: '10px' }}>
                <div
                  className={`progress-fill ${team.readiness_pct >= 100 ? 'success' : team.readiness_pct >= 50 ? 'warning' : 'error'}`}
                  style={{ width: `${Math.min(team.readiness_pct, 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {profile && (
        <div className="card mt-4">
          <h3 className="card-title mb-4">Your Profile</h3>
          <div className="team-info-grid">
            <div className="team-info-row">
              <span className="team-info-label">Name</span>
              <span className="team-info-value">{profile.name}</span>
            </div>
            <div className="team-info-row">
              <span className="team-info-label">Email</span>
              <span className="team-info-value">{profile.email}</span>
            </div>
            <div className="team-info-row">
              <span className="team-info-label">Track Preference</span>
              <span className="team-info-value">{profile.track_pref || 'None'}</span>
            </div>
            <div className="team-info-row">
              <span className="team-info-label">Discord</span>
              <span className="team-info-value">{profile.discord_handle || '—'}</span>
            </div>
          </div>
          {profile.skills?.length > 0 && (
            <div className="mt-4">
              <div className="text-sm text-muted mb-2">Skills</div>
              <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
                {profile.skills.map(s => <span key={s} className="tag">{s}</span>)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
