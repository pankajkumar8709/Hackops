import { useEffect, useState } from 'react'

export default function HealthPage() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>Pulse</h1>
      <p>Backend status: {error ? `ERROR — ${error}` : status ?? 'checking…'}</p>
    </div>
  )
}
