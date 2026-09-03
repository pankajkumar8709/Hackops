import { useState, useRef, useEffect } from 'react'
import { sendChatMessage, fetchMyProfile, reportIssue } from '../api'

export default function ParticipantChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState(null)
  const messagesEnd = useRef(null)

  useEffect(() => {
    fetchMyProfile().then(setProfile).catch(() => {})
    // Welcome message
    setMessages([{
      role: 'bot',
      content: '👋 Welcome to Pulse Chat! Ask me anything about the hackathon — rules, tracks, deadlines, or report a problem.',
      timestamp: new Date(),
    }])
  }, [])

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend(e) {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg = { role: 'user', content: input.trim(), timestamp: new Date() }
    setMessages((prev) => [...prev, userMsg])
    const question = input.trim()
    setInput('')
    setLoading(true)

    try {
      const data = await sendChatMessage(question, profile?.id, profile?.team_id)

      let botContent = data.answer
      if (data.citations?.length > 0) {
        const citation = data.citations[0]
        botContent += `\n\n📎 Source: ${citation.source_doc} (score: ${(citation.similarity_score * 100).toFixed(0)}%)`
      }
      if (!data.confident) {
        botContent += '\n\n⚠️ Low confidence — an issue has been created for organizer review.'
      }

      setMessages((prev) => [...prev, {
        role: 'bot',
        content: botContent,
        confident: data.confident,
        issueCreated: !!data.issue_id,
        timestamp: new Date(),
      }])
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'bot',
        content: `❌ Error: ${err.message}`,
        error: true,
        timestamp: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }

  async function handleReportProblem() {
    const desc = window.prompt('Describe your problem:')
    if (!desc) return

    setLoading(true)
    try {
      await reportIssue({ description: desc, category: 'general', severity: 0.5, is_blocking: false })
      setMessages((prev) => [...prev, {
        role: 'bot',
        content: `✅ Your issue has been reported: "${desc.slice(0, 80)}..."\n\nThe organizer team has been notified and will review it.`,
        timestamp: new Date(),
      }])
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'bot',
        content: `❌ Failed to report: ${err.message}`,
        error: true,
        timestamp: new Date(),
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-page">
      <div className="chat-header">
        <h2>💬 Pulse Chat</h2>
        <button className="btn-sm btn-red" onClick={handleReportProblem}>
          🚨 Report Problem
        </button>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg chat-msg-${msg.role}`}>
            <div className="chat-msg-avatar">
              {msg.role === 'bot' ? '🤖' : '🧑'}
            </div>
            <div className="chat-msg-body">
              <div className="chat-msg-text">
                {msg.content.split('\n').map((line, j) => (
                  <span key={j}>{line}{j < msg.content.split('\n').length - 1 && <br />}</span>
                ))}
              </div>
              <div className="chat-msg-time">
                {msg.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-msg chat-msg-bot">
            <div className="chat-msg-avatar">🤖</div>
            <div className="chat-msg-body">
              <div className="chat-msg-text typing-indicator">
                <span>.</span><span>.</span><span>.</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEnd} />
      </div>

      {/* Input */}
      <form className="chat-input-form" onSubmit={handleSend}>
        <input
          type="text"
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={loading}
          autoFocus
        />
        <button type="submit" className="chat-send-btn" disabled={loading || !input.trim()}>
          Send →
        </button>
      </form>
    </div>
  )
}
