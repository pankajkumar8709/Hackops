import { useState, useEffect } from 'react'
import { fetchMyTeam, fetchMatchSuggestions } from '../api'

export default function ParticipantMatchesPage() {
  const [team, setTeam] = useState(null)
  const [suggestions, setSuggestions] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadSuggestions()
  }, [])

  async function loadSuggestions() {
    setLoading(true)
    setError(null)
    try {
      const teamData = await fetchMyTeam()
      setTeam(teamData)

      if (teamData?.id) {
        const data = await fetchMatchSuggestions(teamData.id)
        setSuggestions(data)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="p-loading">Loading match suggestions…</div>
  if (error) return <div className="p-error">Error: {error}</div>
  if (!team) return <div className="p-empty">You must be in a team to see match suggestions.</div>

  return (
    <div className="p-page">
      <h2 className="p-page-title">🤝 Team Match Suggestions</h2>

      {/* Skill Gap Analysis */}
      {suggestions?.gap_analysis?.missing_skills?.length > 0 ? (
        <div className="p-card">
          <h3 className="p-card-title">🔍 Skill Gaps</h3>
          <p className="p-card-desc">Skills your team needs but doesn't have:</p>
          <div className="p-tag-list">
            {suggestions.gap_analysis.missing_skills.map((gap, i) => (
              <span key={i} className="p-tag p-tag-missing">{gap}</span>
            ))}
          </div>
        </div>
      ) : (
        <div className="p-card">
          <h3 className="p-card-title">✅ No Skill Gaps</h3>
          <p>{suggestions?.message || 'Your team has all the commonly needed skills for this track!'}</p>
        </div>
      )}

      {/* Candidates */}
      <div className="p-card">
        <h3 className="p-card-title">
          👥 Suggested Candidates ({suggestions?.candidates?.length || 0})
        </h3>
        {suggestions?.candidates?.length === 0 ? (
          <div className="p-empty">
            No unassigned participants found with matching skills.
            <br />
            This is normal if all participants are already on teams.
          </div>
        ) : (
          <div className="p-list">
            {suggestions?.candidates?.map((candidate, i) => (
              <div key={candidate.id} className="p-list-item p-border-blue">
                <div className="p-list-header">
                  <span className="p-candidate-rank">#{i + 1}</span>
                  <span className="p-candidate-name">{candidate.name}</span>
                  <span className="p-candidate-score">
                    Match: {(candidate.match_score * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="p-list-text">{candidate.reasoning}</p>
                <div className="p-tag-list">
                  {(candidate.skills || []).map((skill, j) => (
                    <span key={j} className="p-tag p-tag-skill">{skill}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Refresh */}
      <button className="p-refresh-btn" onClick={loadSuggestions} disabled={loading}>
        🔄 Refresh Suggestions
      </button>
    </div>
  )
}
