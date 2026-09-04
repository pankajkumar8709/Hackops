import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { runEventWizard, uploadDocument } from '../../api';
import { useToast } from '../../components/ui/Toast';

const TRACK_FIELDS = [
  { value: 'repo_url', label: 'Repository URL' },
  { value: 'demo_url', label: 'Live Demo URL' },
  { value: 'description', label: 'Description' },
  { value: 'readme_url', label: 'README URL' },
];

const EMPTY_TRACK = { name: '', eligibility_rules: '', required_fields: ['repo_url', 'demo_url', 'description'] };
const EMPTY_MENTOR = { name: '', skills: '', availability_status: 'available', discord_handle: '' };
const EMPTY_POOL = { name: '', resource_type: 'api_key', total_quantity: 5 };

export default function SetupPage() {
  const navigate = useNavigate();
  const toast = useToast();

  const [event, setEvent] = useState({ name: '', current_phase: 'registration', timezone: 'UTC', deadline_at: '' });
  const [tracks, setTracks] = useState([{ ...EMPTY_TRACK }]);
  const [mentors, setMentors] = useState([{ ...EMPTY_MENTOR }]);
  const [pools, setPools] = useState([{ ...EMPTY_POOL }]);
  const [rulesFile, setRulesFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const updateEvent = (field, value) => setEvent(prev => ({ ...prev, [field]: value }));
  const updateItem = (list, setter, index, field, value) => {
    setter(prev => prev.map((item, i) => (i === index ? { ...item, [field]: value } : item)));
  };

  const toggleField = (trackIndex, field) => {
    setTracks(prev => prev.map((t, i) => {
      if (i !== trackIndex) return t;
      const has = t.required_fields.includes(field);
      return { ...t, required_fields: has ? t.required_fields.filter(f => f !== field) : [...t.required_fields, field] };
    }));
  };

  const buildPayload = () => {
    const deadline = event.deadline_at ? new Date(event.deadline_at).toISOString() : null;
    return {
      name: event.name,
      current_phase: event.current_phase,
      timezone: event.timezone || 'UTC',
      deadline_at: deadline,
      tracks: tracks
        .filter(t => t.name.trim())
        .map(t => ({
          name: t.name.trim(),
          eligibility_rules: t.eligibility_rules?.trim() || undefined,
          required_fields: t.required_fields,
        })),
      mentors: mentors
        .filter(m => m.name.trim())
        .map(m => ({
          name: m.name.trim(),
          skills: m.skills ? m.skills.split(',').map(s => s.trim()).filter(Boolean) : [],
          availability_status: m.availability_status,
          discord_handle: m.discord_handle?.trim() || undefined,
        })),
      resource_pools: pools
        .filter(p => p.name.trim())
        .map(p => ({
          name: p.name.trim(),
          resource_type: p.resource_type,
          total_quantity: Math.max(1, parseInt(p.total_quantity, 10) || 1),
        })),
    };
  };

  const handleSubmit = async () => {
    setError('');
    if (!event.name.trim()) {
      setError('Give your event a name to continue.');
      return;
    }
    setSubmitting(true);
    try {
      const result = await runEventWizard(buildPayload());
      toast(`Event "${result.event.name}" created with ${result.tracks.length} track(s).`, 'success');

      if (rulesFile) {
        try {
          await uploadDocument(rulesFile, 'rules');
          toast('Rules document uploaded and ingested.', 'success');
        } catch (e) {
          toast('Event created, but rules upload failed: ' + (e.message || ''), 'error');
        }
      }

      navigate('/organizer?setup=done');
    } catch (err) {
      setError(err.message || 'Setup failed');
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Event Setup</h1>
          <p className="page-subtitle">Go from zero to a fully configured event in one flow</p>
        </div>
      </div>

      {error && <div className="alert alert-error mb-4">{error}</div>}

      <div className="card mb-6">
        <div className="card-header">
          <h2 className="card-title">1 · Event</h2>
        </div>
        <div className="form-row">
          <div className="form-group" style={{ flex: 2 }}>
            <label className="form-label">Event Name *</label>
            <input
              className="form-input"
              placeholder="HackOps 2026"
              value={event.name}
              onChange={(e) => updateEvent('name', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Phase</label>
            <select
              className="form-input form-select"
              value={event.current_phase}
              onChange={(e) => updateEvent('current_phase', e.target.value)}
            >
              <option value="registration">Registration</option>
              <option value="hacking">Hacking</option>
              <option value="judging">Judging</option>
              <option value="finished">Finished</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Submission Deadline</label>
            <input
              className="form-input"
              type="datetime-local"
              value={event.deadline_at}
              onChange={(e) => updateEvent('deadline_at', e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="card mb-6">
        <div className="card-header">
          <h2 className="card-title">2 · Tracks & Submission Requirements</h2>
          <button className="btn btn-ghost btn-sm" onClick={() => setTracks(prev => [...prev, { ...EMPTY_TRACK }])}>
            + Add Track
          </button>
        </div>

        {tracks.map((track, ti) => (
          <div key={ti} className="setup-block">
            <div className="form-row">
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Track Name *</label>
                <input
                  className="form-input"
                  placeholder="AI & Machine Learning"
                  value={track.name}
                  onChange={(e) => updateItem(tracks, setTracks, ti, 'name', e.target.value)}
                />
              </div>
              {tracks.length > 1 && (
                <div style={{ alignSelf: 'flex-end', marginBottom: '8px' }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => setTracks(prev => prev.filter((_, i) => i !== ti))}>
                    Remove
                  </button>
                </div>
              )}
            </div>
            <div className="form-group">
              <label className="form-label">Eligibility Rules (optional)</label>
              <textarea
                className="form-input form-textarea"
                rows={2}
                placeholder="Skills or constraints teams must meet..."
                value={track.eligibility_rules}
                onChange={(e) => updateItem(tracks, setTracks, ti, 'eligibility_rules', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Required Submission Fields</label>
              <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                {TRACK_FIELDS.map(f => {
                  const active = track.required_fields.includes(f.value);
                  return (
                    <button
                      key={f.value}
                      type="button"
                      className={`badge ${active ? 'badge-primary' : 'badge-neutral'}`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => toggleField(ti, f.value)}
                    >
                      {active ? '✓ ' : ''}{f.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card mb-6">
        <div className="card-header">
          <h2 className="card-title">3 · Mentors</h2>
          <button className="btn btn-ghost btn-sm" onClick={() => setMentors(prev => [...prev, { ...EMPTY_MENTOR }])}>
            + Add Mentor
          </button>
        </div>
        {mentors.map((mentor, mi) => (
          <div key={mi} className="setup-block">
            <div className="form-row">
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Mentor Name</label>
                <input
                  className="form-input"
                  placeholder="Dr. Sarah Chen"
                  value={mentor.name}
                  onChange={(e) => updateItem(mentors, setMentors, mi, 'name', e.target.value)}
                />
              </div>
              <div className="form-group" style={{ flex: 2 }}>
                <label className="form-label">Skills (comma separated)</label>
                <input
                  className="form-input"
                  placeholder="python, fastapi, machine learning"
                  value={mentor.skills}
                  onChange={(e) => updateItem(mentors, setMentors, mi, 'skills', e.target.value)}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card mb-6">
        <div className="card-header">
          <h2 className="card-title">4 · Resource Pools</h2>
          <button className="btn btn-ghost btn-sm" onClick={() => setPools(prev => [...prev, { ...EMPTY_POOL }])}>
            + Add Pool
          </button>
        </div>
        {pools.map((pool, pi) => (
          <div key={pi} className="setup-block">
            <div className="form-row">
              <div className="form-group" style={{ flex: 2 }}>
                <label className="form-label">Pool Name</label>
                <input
                  className="form-input"
                  placeholder="Groq API Keys"
                  value={pool.name}
                  onChange={(e) => updateItem(pools, setPools, pi, 'name', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select
                  className="form-input form-select"
                  value={pool.resource_type}
                  onChange={(e) => updateItem(pools, setPools, pi, 'resource_type', e.target.value)}
                >
                  <option value="api_key">API Key</option>
                  <option value="cloud_credit">Cloud Credit</option>
                  <option value="hardware_kit">Hardware Kit</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="form-group" style={{ maxWidth: '120px' }}>
                <label className="form-label">Quantity</label>
                <input
                  className="form-input"
                  type="number"
                  min="1"
                  value={pool.total_quantity}
                  onChange={(e) => updateItem(pools, setPools, pi, 'total_quantity', e.target.value)}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card mb-6">
        <div className="card-header">
          <h2 className="card-title">5 · Rules Document (optional)</h2>
        </div>
        <p className="text-sm text-muted mb-3">
          Upload the official rules — Pulse will ingest it and answer participant questions from it.
        </p>
        <input
          className="form-input"
          type="file"
          accept=".txt,.md,.pdf"
          onChange={(e) => setRulesFile(e.target.files?.[0] || null)}
        />
      </div>

      <div className="flex items-center gap-3">
        <button className="btn btn-primary btn-lg" onClick={handleSubmit} disabled={submitting}>
          {submitting ? <><span className="loading-spinner" /> Creating event...</> : 'Create Event'}
        </button>
        <Link to="/organizer" className="btn btn-secondary btn-lg">Cancel</Link>
      </div>
    </div>
  );
}
