import { useState, useRef, useEffect } from 'react';
import { sendChatMessage, fetchMyProfile } from '../../api';
import { LoadingSpinner } from '../../components/ui/States';

export default function ParticipantChatPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchMyProfile().then(setProfile).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setLoading(true);

    try {
      const res = await sendChatMessage(question, profile?.id, profile?.team_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        confident: res.confident,
        issueId: res.issue_id,
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${err.message}`,
        confident: false,
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div>
          <h2 className="page-title">HackOps Assistant</h2>
          <p className="page-subtitle">Ask about rules, resources, submissions, mentors, or the event.</p>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state" style={{ padding: '40px' }}>
            <div style={{ fontSize: '36px', marginBottom: '12px' }}>💬</div>
            <h3 className="empty-title">How can I help?</h3>
            <p className="empty-desc">Ask me anything about the hackathon — rules, submission requirements, timelines, resources, or team formation.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role === 'user' ? 'chat-msg-user' : 'chat-msg-bot'}`}>
            <div className="avatar avatar-sm" style={{ background: msg.role === 'user' ? 'var(--primary)' : 'var(--bg-elevated)', color: msg.role === 'user' ? 'white' : 'var(--text-primary)' }}>
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>
            <div>
              <div className="chat-msg-bubble">
                <div className="chat-msg-text" style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
              </div>

              {msg.role === 'assistant' && (
                <>
                  {msg.citations?.length > 0 && (
                    <div className="chat-citations">
                      <div className="chat-citation-label">📚 Sources</div>
                      {msg.citations.map((c, j) => (
                        <div key={j} className="chat-citation-item">
                          <strong>{c.source_doc}</strong> — {c.chunk_text?.slice(0, 120)}...
                          <span className="text-muted"> ({(c.similarity_score * 100).toFixed(0)}% match)</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="chat-msg-meta">
                    <span className={`badge badge-sm ${msg.confident ? 'badge-success' : 'badge-warning'}`}>
                      {msg.confident ? '✓ Confident' : '⚠ Low confidence'}
                    </span>
                    {msg.issueId && (
                      <span className="badge badge-sm badge-info ml-2">Issue created</span>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-msg chat-msg-bot">
            <div className="avatar avatar-sm">🤖</div>
            <div className="chat-msg-bubble">
              <div className="typing-indicator">
                <span>●</span><span>●</span><span>●</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-bar" onSubmit={handleSend}>
        <input
          className="form-input"
          placeholder="Ask a question..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="btn btn-primary" disabled={loading || !input.trim()}>
          {loading ? <span className="loading-spinner" /> : 'Send'}
        </button>
      </form>
    </div>
  );
}
