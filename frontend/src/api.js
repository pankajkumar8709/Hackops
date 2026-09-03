/**
 * API client for Pulse backend.
 * Handles auth token, WebSocket, and all dashboard endpoints.
 */

const BASE = '/api';

let _token = null;

export function getToken() {
  if (!_token) _token = localStorage.getItem('pulse_token');
  return _token;
}

export function setToken(token) {
  _token = token;
  localStorage.setItem('pulse_token', token);
}

export function clearToken() {
  _token = null;
  localStorage.removeItem('pulse_token');
}

async function request(path, opts = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...opts.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (res.headers.get('content-type')?.includes('text/csv')) {
    return res.blob();
  }
  return res.json();
}

// ─── Auth ───────────────────────────────────────────────

export async function loginOrganizer(username, password) {
  const data = await request('/auth/organizer/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  setToken(data.access_token);
  return data;
}

// ─── Dashboard ──────────────────────────────────────────

export function fetchDashboardHealth() {
  return request('/dashboard/health');
}

export function fetchApprovalQueue() {
  return request('/dashboard/approval-queue');
}

export function fetchEscalations(status) {
  const qs = status ? `?status=${status}` : '';
  return request(`/escalations${qs}`);
}

export function fetchAgentActions(limit = 50) {
  return request(`/orchestrator/actions?limit=${limit}`);
}

export function fetchOrchestratorStatus() {
  return request('/orchestrator/status');
}

// ─── Overrides ──────────────────────────────────────────

export function overrideTeam(teamId, data) {
  return request(`/dashboard/teams/${teamId}/override`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function overrideSubmission(submissionId, data) {
  return request(`/dashboard/submissions/${submissionId}/override`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

// ─── Broadcast ──────────────────────────────────────────

export function broadcastMessage(message, channel = 'in_app') {
  return request('/dashboard/broadcast', {
    method: 'POST',
    body: JSON.stringify({ message, channel }),
  });
}

// ─── Export ─────────────────────────────────────────────

export async function exportSubmissionsCSV() {
  const blob = await request('/dashboard/export');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'submissions_export.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Escalation resolve ─────────────────────────────────

export function resolveEscalation(escalationId, resolutionNotes) {
  return request(`/escalations/${escalationId}/resolve`, {
    method: 'PATCH',
    body: JSON.stringify({ resolution_notes: resolutionNotes }),
  });
}

// ─── Orchestrator ───────────────────────────────────────

export function runOrchestrator(triggerType, context) {
  return request('/orchestrator/run', {
    method: 'POST',
    body: JSON.stringify({ trigger_type: triggerType, context }),
  });
}

export function runSweep() {
  return request('/orchestrator/sweep', { method: 'POST' });
}

// ─── WebSocket ──────────────────────────────────────────

// ─── Participant: Chat (Q&A) ────────────────────────────

export function sendChatMessage(question, participantId, teamId) {
  return request('/qa', {
    method: 'POST',
    body: JSON.stringify({
      question,
      participant_id: participantId || undefined,
      team_id: teamId || undefined,
    }),
  });
}

// ─── Participant: Team Status ────────────────────────────

export function fetchMyTeam() {
  return request('/teams/mine');
}

export function fetchMySubmission() {
  return request('/submissions/mine');
}

export function fetchMyIssues() {
  return request('/issues/mine');
}

export function fetchMyResourceAllocations() {
  return request('/resource-requests/mine');
}

export function fetchMyNotifications() {
  return request('/notifications/mine');
}

export function markNotificationRead(notificationId) {
  return request(`/notifications/${notificationId}/read`, { method: 'PATCH' });
}

// ─── Participant: Match Suggestions ──────────────────────

export function fetchMatchSuggestions(teamId) {
  return request(`/teams/${teamId}/match-suggestions`);
}

// ─── Participant: Profile ────────────────────────────────

export function fetchMyProfile() {
  return request('/participants/me');
}

// ─── Participant: Issue Creation ─────────────────────────

export function reportIssue(data) {
  return request('/issues', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ─── Participant: Resource Request ───────────────────────

export function requestResource(resourceItemId) {
  return request('/resource-requests', {
    method: 'POST',
    body: JSON.stringify({ resource_item_id: resourceItemId }),
  });
}

// ─── WebSocket ──────────────────────────────────────────

export function createDashboardWS(onMessage) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  // Vite proxy: frontend is on 5173, backend on 8000
  const ws = new WebSocket(`${protocol}//localhost:8000/dashboard/ws`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.warn('WS parse error:', e);
    }
  };

  ws.onerror = (err) => {
    console.warn('WS error (server may not support WebSocket):', err);
  };

  // Ping every 30s to keep alive
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send('ping');
  }, 30000);

  ws._cleanup = () => {
    clearInterval(pingInterval);
    ws.close();
  };

  return ws;
}
