/**
 * HackOps API Client
 * Complete integration with all backend endpoints.
 */

const BASE = '/api';

// Tokens are stored per-role so an organizer JWT can never be mistaken for
// a participant JWT (and vice-versa) by a later route guard.
const ORG_KEY = 'hackops_org_token';
const PART_KEY = 'hackops_participant_token';
const ROLE_KEY = 'hackops_role';

let _token = null;
let _role = null;

// ─── Token Management ────────────────────────────────────

export function getRole() {
  if (!_role) _role = localStorage.getItem(ROLE_KEY);
  return _role;
}

/** Return the token for the currently active role (never a mix). */
export function getToken() {
  if (!_token) {
    const role = getRole();
    _token = role === 'organizer' ? localStorage.getItem(ORG_KEY) : localStorage.getItem(PART_KEY);
  }
  return _token;
}

/** Store an organizer JWT under its own key. */
export function setOrganizerToken(token) {
  if (!token) return;
  _token = token;
  _role = 'organizer';
  localStorage.setItem(ORG_KEY, token);
  localStorage.setItem(ROLE_KEY, 'organizer');
  localStorage.removeItem(PART_KEY);
}

/** Store a participant JWT under its own key. */
export function setParticipantToken(token) {
  if (!token) return;
  _token = token;
  _role = 'participant';
  localStorage.setItem(PART_KEY, token);
  localStorage.setItem(ROLE_KEY, 'participant');
  localStorage.removeItem(ORG_KEY);
}

// Legacy alias used by older pages; routes by role.
export function setToken(token, role) {
  if (!token) return;
  if (role === 'organizer') setOrganizerToken(token);
  else setParticipantToken(token);
}

export function clearToken() {
  _token = null;
  _role = null;
  localStorage.removeItem(ORG_KEY);
  localStorage.removeItem(PART_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function isOrganizer() {
  return getRole() === 'organizer';
}

export function isParticipant() {
  return getRole() === 'participant';
}

// ─── Core Request ────────────────────────────────────────

async function request(path, opts = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...opts.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {}
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  if (res.headers.get('content-type')?.includes('text/csv')) {
    return res.blob();
  }
  return res.json();
}

// ─── Auth ────────────────────────────────────────────────

export async function loginOrganizer(username, password) {
  const data = await request('/auth/organizer/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  setOrganizerToken(data.access_token);
  return data;
}

/**
 * Participant login: registered email + password.
 * The backend exchanges them for a participant JWT — only that JWT is stored.
 */
export async function loginParticipant(email, password) {
  const data = await request('/auth/participant/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setParticipantToken(data.access_token);
  return data;
}

/**
 * Register a participant with email and password.
 * Follow up with loginParticipant(email, password).
 */
export async function registerParticipant(data) {
  return request('/participants/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function loginWithToken(token, role) {
  if (role === 'organizer') setOrganizerToken(token);
  else setParticipantToken(token);
}

// ─── Participants ────────────────────────────────────────

export function fetchMyProfile() {
  return request('/participants/me');
}

export function fetchAllParticipants() {
  return request('/participants');
}

export function fetchParticipant(id) {
  return request(`/participants/${id}`);
}

// ─── Teams ───────────────────────────────────────────────

export function createTeam(name, trackId) {
  return request('/teams', {
    method: 'POST',
    body: JSON.stringify({ name, track_id: trackId || undefined }),
  });
}

export function joinTeam(teamId) {
  return request(`/teams/${teamId}/join`, { method: 'POST' });
}

export function fetchMyTeam() {
  return request('/teams/mine');
}

export function fetchAllTeams() {
  return request('/teams');
}

export function fetchTeam(teamId) {
  return request(`/teams/${teamId}`);
}

// ─── Events & Tracks ────────────────────────────────────

export function fetchAllEvents() {
  return request('/events');
}

export function fetchAllTracks() {
  return request('/tracks');
}

export function fetchScheduleEvents() {
  return request('/schedule-events');
}

export function fetchSubmissionRequirements(trackId) {
  const qs = trackId ? `?track_id=${trackId}` : '';
  return request(`/submission-requirements${qs}`);
}

// ─── Documents ───────────────────────────────────────────

export function fetchAllDocuments() {
  return request('/documents');
}

export async function uploadDocument(file, docType = 'rules') {
  const token = getToken();
  const formData = new FormData();
  formData.append('file', file);
  formData.append('doc_type', docType);

  const res = await fetch(`${BASE}/documents`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function deleteDocument(docId) {
  return request(`/documents/${docId}`, { method: 'DELETE' });
}

// ─── Mentors ─────────────────────────────────────────────

export function fetchAllMentors() {
  return request('/mentors');
}

export function createMentor(data) {
  return request('/mentors', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateMentor(id, data) {
  return request(`/mentors/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

// ─── Resources ───────────────────────────────────────────

export function fetchAllResources() {
  return request('/resources');
}

export function fetchAvailableResources() {
  return request('/resources/available');
}

export function createResource(data) {
  return request('/resources', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ─── Q&A / AI Assistant ─────────────────────────────────

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

// ─── Submissions ─────────────────────────────────────────

export function fetchMySubmission() {
  return request('/submissions/mine');
}

export function createOrUpdateSubmission(data) {
  return request('/submissions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSubmission(id, data) {
  return request(`/submissions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function fetchSubmissionAudit(id) {
  return request(`/submissions/${id}/audit`);
}

export function fetchAllSubmissions() {
  return request('/submissions');
}

export function fetchSubmissionAuditOrganizer(id) {
  return request(`/submissions/${id}/audit-organizer`);
}

// ─── Issues & Escalations ────────────────────────────────

export function reportIssue(data) {
  return request('/issues', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function fetchMyIssues() {
  return request('/issues/mine');
}

export function fetchIssue(id) {
  return request(`/issues/${id}`);
}

export function fetchEscalations(status) {
  const qs = status ? `?status=${status}` : '';
  return request(`/escalations${qs}`);
}

export function resolveEscalation(id, resolutionNotes, assignment) {
  return request(`/escalations/${id}/resolve`, {
    method: 'PATCH',
    body: JSON.stringify({
      resolution_notes: resolutionNotes || '',
      assigned_organizer: assignment || undefined,
    }),
  });
}

// ─── Mentor Allocations ──────────────────────────────────

export function requestMentorAllocation(issueId) {
  return request('/mentor-allocations', {
    method: 'POST',
    body: JSON.stringify({ issue_id: issueId }),
  });
}

export function fetchMyAllocations(statusFilter) {
  const qs = statusFilter ? `?status=${statusFilter}` : '';
  return request(`/mentor-allocations/mine${qs}`);
}

export function fetchAllAllocations(statusFilter) {
  const qs = statusFilter ? `?status=${statusFilter}` : '';
  return request(`/mentor-allocations${qs}`);
}

export function acceptAllocation(id, notes) {
  return request(`/mentor-allocations/${id}/accept`, {
    method: 'PATCH',
    body: JSON.stringify({ notes: notes || undefined }),
  });
}

export function declineAllocation(id, reason) {
  return request(`/mentor-allocations/${id}/decline`, {
    method: 'PATCH',
    body: JSON.stringify({ reason }),
  });
}

export function triggerTimeoutCheck() {
  return request('/mentor-allocations/check-timeouts', { method: 'POST' });
}

// ─── Resource Requests ───────────────────────────────────

export function requestResource(resourceItemId) {
  return request('/resource-requests', {
    method: 'POST',
    body: JSON.stringify({ resource_item_id: resourceItemId }),
  });
}

export function fetchMyResourceAllocations(statusFilter) {
  const qs = statusFilter ? `?status=${statusFilter}` : '';
  return request(`/resource-requests/mine${qs}`);
}

export function returnResource(id) {
  return request(`/resource-requests/${id}/return`, { method: 'PATCH' });
}

export function fetchAllResourceAllocations(statusFilter) {
  const qs = statusFilter ? `?status=${statusFilter}` : '';
  return request(`/resource-requests${qs}`);
}

export function fetchResourcePools() {
  return request('/resource-pools');
}

export function triggerOverdueCheck() {
  return request('/resource-requests/check-overdue', { method: 'POST' });
}

// ─── Reminders & Notifications ───────────────────────────

export function triggerReminderSweep(data) {
  return request('/reminders/sweep', {
    method: 'POST',
    body: JSON.stringify(data || { threshold_hours: 24, completeness_threshold: 100 }),
  });
}

export function fetchSweepHistory() {
  return request('/reminders');
}

export function fetchMyNotifications(unreadOnly) {
  const qs = unreadOnly ? '?unread_only=true' : '';
  return request(`/notifications/mine${qs}`);
}

export function markNotificationRead(id) {
  return request(`/notifications/${id}/read`, { method: 'PATCH' });
}

export function fetchAllNotifications(limit) {
  const qs = limit ? `?limit=${limit}` : '';
  return request(`/notifications/all${qs}`);
}

export function sendNotification(data) {
  return request('/notifications/send', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function fetchPendingNotifications(channel) {
  const qs = channel ? `?channel=${channel}` : '';
  return request(`/notifications/pending${qs}`);
}

export function fetchChannelStatus() {
  return request('/notifications/channels');
}

// ─── Orchestrator ────────────────────────────────────────

export function runOrchestrator(triggerType, context) {
  return request('/orchestrator/run', {
    method: 'POST',
    body: JSON.stringify({ trigger_type: triggerType, context }),
  });
}

export function runSweep() {
  return request('/orchestrator/sweep', { method: 'POST' });
}

export function fetchAgentActions(limit = 50, actionType) {
  let qs = `?limit=${limit}`;
  if (actionType) qs += `&action_type=${actionType}`;
  return request(`/orchestrator/actions${qs}`);
}

export function fetchOrchestratorStatus() {
  return request('/orchestrator/status');
}

// ─── Event Setup ─────────────────────────────────────────

export function createEvent(data) {
  return request('/events', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateEvent(id, data) {
  return request(`/events/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function createTrack(data) {
  return request('/tracks', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function addSubmissionRequirement(data) {
  return request('/submission-requirements', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** One-call guided setup: event + tracks + requirements + mentors + pools. */
export function runEventWizard(data) {
  return request('/events/wizard', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ─── Dashboard ───────────────────────────────────────────

export function fetchDashboardHealth() {
  return request('/dashboard/health');
}

export function fetchApprovalQueue() {
  return request('/dashboard/approval-queue');
}

export function approveApprovalItem(id, note) {
  const qs = note ? `?note=${encodeURIComponent(note)}` : '';
  return request(`/dashboard/approval-queue/${id}/approve${qs}`, { method: 'PATCH' });
}

export function rejectApprovalItem(id, note) {
  const qs = note ? `?note=${encodeURIComponent(note)}` : '';
  return request(`/dashboard/approval-queue/${id}/reject${qs}`, { method: 'PATCH' });
}

export function broadcastMessage(message, channel = 'in_app') {
  return request('/dashboard/broadcast', {
    method: 'POST',
    body: JSON.stringify({ message, channel }),
  });
}

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

export async function exportSubmissionsCSV() {
  const blob = await request('/dashboard/export');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'submissions_export.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Match Suggestions ───────────────────────────────────

export function fetchMatchSuggestions(teamId) {
  return request(`/teams/${teamId}/match-suggestions`);
}

// ─── WebSocket ───────────────────────────────────────────

/**
 * Open the live dashboard WebSocket.
 *
 * The URL is derived from the current origin (works behind the Vite /api
 * proxy and in production) and carries the organizer JWT as a query param.
 * `onStatus` is called with 'connecting' | 'connected' | 'closed' | 'error'
 * so the UI can surface connection failures instead of silently falling
 * back to polling.
 */
export function createDashboardWS({ onMessage, onStatus }) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${window.location.host}/api/dashboard/ws?token=${encodeURIComponent(getToken() || '')}`;
  const ws = new WebSocket(url);

  if (onStatus) onStatus('connecting');

  ws.onopen = () => { if (onStatus) onStatus('connected'); };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (onMessage) onMessage(data);
    } catch {}
  };

  ws.onerror = () => { if (onStatus) onStatus('error'); };
  ws.onclose = () => { if (onStatus) onStatus('closed'); };

  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send('ping');
  }, 30000);

  ws._cleanup = () => {
    clearInterval(pingInterval);
    ws.close();
  };

  return ws;
}

// ─── Health Check ────────────────────────────────────────

export function fetchHealth() {
  return request('/health');
}
