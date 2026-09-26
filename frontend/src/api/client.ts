const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export interface DevUser {
  user_key: string;
  display_name: string;
  role_hint: string;
}
export interface DevOutboxMessage { id: string; created_at: string; text: string; buttons: Array<{ text: string; start_param: string | null }>; }

export interface AuthUser {
  id: string;
  display_name: string;
  photo_url: string | null;
  staff: { role: string; organization: string; position: string | null; verified: boolean } | null;
}

export interface TokenResponse {
  access_token: string;
  expires_at: string;
  user: AuthUser;
}

export interface ServiceSummary {
  code: string;
  version: number;
  title: string;
  short_description: string;
  steps_count: number;
  estimated_minutes: number;
  is_demo: boolean;
}

export type ElementType =
  | 'text'
  | 'number'
  | 'date'
  | 'select'
  | 'radio'
  | 'checkbox'
  | 'otp'
  | 'info'
  | 'summary'
  | 'action';

export interface ServiceOption {
  value: string;
  label: string;
}

export interface VisibleIf {
  element: string;
  equals?: unknown;
  in?: unknown[];
}

export interface ServiceElement {
  id: string;
  type: ElementType;
  label?: string;
  hint?: string;
  placeholder?: string;
  unit?: string;
  text?: string;
  style?: 'info' | 'warning';
  required?: boolean;
  privacy?: 'public' | 'masked' | 'owner_only';
  options?: ServiceOption[];
  visible_if?: VisibleIf;
  action_policy?: 'owner_only';
}

export interface ServiceStep {
  id: string;
  title: string;
  description?: string;
  elements: ServiceElement[];
}

export interface ServiceDefinition extends Omit<ServiceSummary, 'steps_count' | 'is_demo'> {
  disclaimer?: string;
  steps: ServiceStep[];
}

export interface FieldError {
  element_id: string;
  code: string;
  message: string;
  details?: string;
}

export interface ServiceSession {
  id: string;
  service: { code: string; version: number; title: string };
  status: 'draft' | 'submitted' | 'cancelled';
  current_step: { id: string; index: number; title: string };
  total_steps: number;
  steps: Array<{ id: string; index: number; title: string; status: 'completed' | 'current' | 'upcoming' }>;
  values: Record<string, unknown>;
  errors: FieldError[];
  active_assist_session_id: string | null;
  application_number: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
}

export interface ConfirmationCode {
  expires_at: string;
  resend_available_at: string;
}

export interface InboxMessage {
  id: string;
  text: string;
  created_at: string;
}

export interface SubmitResult {
  status: 'submitted';
  application_number: string;
  submitted_at: string;
}

export interface Me extends AuthUser {
  first_name: string;
  last_name: string;
  recording_consent: boolean;
  counters: {
    drafts: number;
    active_assist_sessions: number;
    trusted_helpers: number;
    helping_for: number;
  };
}

export interface Person {
  id: string;
  display_name: string;
  photo_url: string | null;
}

export interface AssistParticipant extends Person {
  role: string;
  status: string;
  badge: { label: string; verified: boolean } | null;
  online: boolean;
}

export interface AssistSession {
  id: string;
  status: 'waiting' | 'active' | 'ended';
  service: { code: string; title: string };
  service_session_id: string | null;
  owner: Person;
  current_step: { id: string; index: number; title: string } | null;
  total_steps: number;
  me: { participant_id: string; role: string; status: string; capabilities: string[] };
  participants: AssistParticipant[];
  pending_invites: Array<{ id: string; kind: string; expires_at: string }> | null;
  recording: { status: string; duration_ms: number | null } | null;
  ws_url: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  end_reason: string | null;
}

export interface ActiveAssist {
  id: string;
  status: string;
  my_role: string;
  my_status: string;
  service_title: string;
  owner_display_name: string;
  current_step: { index: number; title: string };
  total_steps: number;
}

export interface AssistInvite {
  id: string;
  kind: string;
  token: string;
  deep_link: string;
  share_text: string;
  expires_at: string;
  delivery: 'share_required' | 'bot_message';
}
export interface TrustedHelper { id: string; helper: Person; alias: string | null; verification_method: string; created_at: string; last_helped_at: string | null; }
export interface HelpingFor { id: string; owner: Omit<Person, 'id'>; active_assist_session_id: string | null; created_at: string; }
export interface Pairing { id: string; method: 'qr' | 'link'; status: string; token: string; qr_payload: string; deep_link: string; expires_at: string; }
export interface PairingState { id: string; status: string; expires_at: string; claimed_by: { display_name: string; photo_url: string | null; max_username: string | null } | null; }
export interface PairingPreview { status: string; owner: { display_name: string; photo_url: string | null }; }

export interface InvitePreview {
  status: 'valid' | 'expired' | 'used' | 'declined' | 'revoked' | 'session_ended';
  assist_session_id: string;
  owner: Omit<Person, 'id'>;
  service: { title: string };
  current_step: { index: number; total: number; title: string };
  is_owner: boolean;
  you_are_trusted: boolean;
  requires_owner_approval: boolean;
  expires_at: string;
}

export interface InviteAcceptance {
  assist_session_id: string;
  participant_id: string;
  status: 'pending' | 'active';
}

export interface ProjectedElement extends Omit<ServiceElement, 'options'> {
  options: ServiceOption[] | null;
  view: { state: 'filled' | 'empty' | 'hidden'; value: unknown; locked: boolean } | null;
  rows: Array<{
    element_id: string;
    step_id: string;
    label: string;
    view: { state: 'filled' | 'empty' | 'hidden'; value: unknown; locked: boolean };
  }> | null;
  action: { label: string; available: boolean; reason: string | null } | null;
  operator_hint: string | null;
}

export interface ProjectedState {
  last_seq: number;
  session: AssistSession;
  service: { code: string; version: number; title: string; total_steps: number };
  steps: Array<{ id: string; index: number; title: string; status: 'completed' | 'current' | 'upcoming' }>;
  current_step: {
    id: string;
    index: number;
    title: string;
    description: string | null;
    operator_hint: string | null;
    elements: ProjectedElement[];
  };
  errors: FieldError[];
  annotations: Array<{
    id: string;
    kind: string;
    element_id: string;
    label: string | null;
    author: { participant_id: string; role: string; display_name: string };
    expires_at: string | null;
  }>;
  operator_request: { id: string; status: string; topic: string; position: number | null } | null;
  service_session_status: string;
}

export interface ConsultationSummary {
  assist_session_id: string;
  service: { title: string };
  status: string;
  end_reason: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_sec: number;
  helpers: Array<{ display_name: string; role: string; badge: { label: string; verified: boolean } | null }>;
  steps_completed: number | null;
  total_steps: number;
  stopped_at_step: { id: string; index: number; title: string } | null;
  service_session_status: string;
  recording: { status: string; duration_ms: number | null } | null;
  actions: { can_continue: boolean; can_call_again: Array<{ trusted_helper_id: string; display_name: string }> };
}
export interface ConsultationListItem extends ConsultationSummary { my_role: string; owner_display_name: string | null; stats: { highlights: number; confusions: number }; }
export interface ConsultationDetail extends ConsultationSummary { chapters: Array<{ step_id: string; title: string; start_offset_ms: number; duration_ms: number; highlights: number; confusions: number; had_errors: boolean }>; }
export interface ConsultationReplay { assist_session_id: string; service: { code: string; title: string }; duration_ms: number; steps: Array<{ id: string; index: number; title: string; elements: Array<{ id: string; type: string; label: string | null }> }>; recording: { status: string; url: string | null; offset_ms: number | null; duration_ms: number | null } | null; events: Array<{ seq: number | null; offset_ms: number; type: string; payload: Record<string, unknown> }>; }

export interface OperatorQueueItem {
  id: string;
  status: string;
  source: string;
  topic: 'dont_understand' | 'form_error' | 'other';
  created_at: string;
  waiting_sec: number;
  context: { owner_display_name: string; service_title: string; step: { index: number; total: number; title: string } | null; error_codes: string[]; ai_summary: string | null };
}

export interface OperatorRequest { id: string; status: string; topic: string; position: number | null; }
export interface HelpCallback {
  id: string;
  status: 'busy' | 'ready';
  owner: { display_name: string };
  helper: { display_name: string };
  service_session_id: string;
  service: { title: string };
  created_at: string;
  ready_at: string | null;
  expires_at: string;
}
export interface VoiceToken { url: string; room: string; token: string; expires_at: string; }
export interface PastHelpFragment { assist_session_id: string; date: string; helpers: Array<{ display_name: string; role: string }>; has_audio: boolean; audio_url: string | null; audio_start_ms: number | null; audio_end_ms: number | null; replay_from_ms: number; replay_to_ms: number; highlights: number; confusions: number; }
export interface PastHelp { steps: Record<string, PastHelpFragment[]>; }

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
  }
}

let accessToken = '';

export function getAccessToken(): string {
  return accessToken;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('content-type', 'application/json');
  if (accessToken) headers.set('authorization', `Bearer ${accessToken}`);

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Ошибка запроса (${response.status})`;
    let code: string | undefined;
    let details: Record<string, unknown> | undefined;
    try {
      const payload = (await response.json()) as {
        error?: { message?: string; code?: string; details?: Record<string, unknown> };
      };
      message = payload.error?.message ?? message;
      code = payload.error?.code;
      details = payload.error?.details;
    } catch {
      // Keep the status-based message when the server did not return JSON.
    }
    throw new ApiError(message, response.status, code, details);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function finishLogin(payload: TokenResponse): TokenResponse {
  accessToken = payload.access_token;
  return payload;
}

export function loginWithMax(initData: string): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/max', {
    method: 'POST',
    body: JSON.stringify({ init_data: initData }),
  }).then(finishLogin);
}

export function loginWithDev(userKey: string): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/dev-login', {
    method: 'POST',
    body: JSON.stringify({ user_key: userKey }),
  }).then(finishLogin);
}

export function getDevUsers(signal?: AbortSignal): Promise<DevUser[]> {
  return request<DevUser[]>('/dev/users', { signal });
}
export function getDevOutbox(signal?: AbortSignal): Promise<DevOutboxMessage[]> { return request<DevOutboxMessage[]>('/dev/outbox', { signal }); }

export function getMe(signal?: AbortSignal): Promise<Me> {
  return request<Me>('/me', { signal });
}

export function agreeToRecording(): Promise<void> {
  return request<void>('/me/recording-consent', { method: 'POST' });
}

export function getServices(signal?: AbortSignal): Promise<ServiceSummary[]> {
  return request<ServiceSummary[]>('/services', { signal });
}

export function getService(code: string, signal?: AbortSignal): Promise<ServiceDefinition> {
  return request<ServiceDefinition>(`/services/${code}`, { signal });
}

export function getServiceSessions(signal?: AbortSignal): Promise<ServiceSession[]> {
  return request<ServiceSession[]>('/service-sessions', { signal });
}

export function getServiceSession(id: string, signal?: AbortSignal): Promise<ServiceSession> {
  return request<ServiceSession>(`/service-sessions/${id}`, { signal });
}

export function startServiceSession(serviceCode: string): Promise<ServiceSession> {
  return request<ServiceSession>('/service-sessions', {
    method: 'POST',
    body: JSON.stringify({ service_code: serviceCode }),
  });
}

export function deleteServiceSession(sessionId: string): Promise<void> {
  return request<void>(`/service-sessions/${sessionId}`, { method: 'DELETE' });
}

export function updateServiceFields(
  sessionId: string,
  values: Record<string, unknown>,
  version: number,
): Promise<ServiceSession> {
  return request<ServiceSession>(`/service-sessions/${sessionId}/fields`, {
    method: 'PATCH',
    body: JSON.stringify({ values, version }),
  });
}

export function navigateService(
  sessionId: string,
  action: 'next' | 'back' | 'goto',
  stepId?: string,
): Promise<ServiceSession> {
  return request<ServiceSession>(`/service-sessions/${sessionId}/navigation`, {
    method: 'POST',
    body: JSON.stringify({ action, ...(stepId ? { step_id: stepId } : {}) }),
  });
}

export function issueConfirmationCode(sessionId: string): Promise<ConfirmationCode> {
  return request<ConfirmationCode>(`/service-sessions/${sessionId}/confirmation-code`, { method: 'POST' });
}

export function getDemoInbox(sessionId: string, signal?: AbortSignal): Promise<InboxMessage[]> {
  return request<InboxMessage[]>(`/service-sessions/${sessionId}/demo-inbox`, { signal });
}

export function submitService(sessionId: string, confirmationCode: string): Promise<SubmitResult> {
  return request<SubmitResult>(`/service-sessions/${sessionId}/submit`, {
    method: 'POST',
    body: JSON.stringify({ confirmation_code: confirmationCode }),
  });
}

export function createAssistSession(serviceSessionId: string): Promise<AssistSession> {
  return request<AssistSession>('/assist-sessions', {
    method: 'POST',
    body: JSON.stringify({ service_session_id: serviceSessionId }),
  });
}
export function callDigitalEmployee(serviceSessionId: string): Promise<{ assist_session: AssistSession }> { return request(`/service-sessions/${serviceSessionId}/ai-agent`, { method: 'POST' }); }
export function releaseDigitalEmployee(assistId: string): Promise<void> { return request<void>(`/assist-sessions/${assistId}/ai-agent`, { method: 'DELETE' }); }

export function getActiveAssistSessions(signal?: AbortSignal): Promise<ActiveAssist[]> {
  return request<ActiveAssist[]>('/assist-sessions?scope=active', { signal });
}

export function getAssistSession(id: string, signal?: AbortSignal): Promise<AssistSession> {
  return request<AssistSession>(`/assist-sessions/${id}`, { signal });
}

export function getAssistState(id: string, signal?: AbortSignal): Promise<ProjectedState> {
  return request<ProjectedState>(`/assist-sessions/${id}/state`, { signal });
}

export function createAssistInvite(id: string, trustedHelperId?: string): Promise<AssistInvite> {
  return request<AssistInvite>(`/assist-sessions/${id}/invites`, {
    method: 'POST',
    body: JSON.stringify(trustedHelperId ? { kind: 'trusted_call', trusted_helper_id: trustedHelperId } : { kind: 'link' }),
  });
}

export function getTrustedHelpers(signal?: AbortSignal): Promise<TrustedHelper[]> { return request<TrustedHelper[]>('/trusted-helpers', { signal }); }
export function getHelpingFor(signal?: AbortSignal): Promise<HelpingFor[]> { return request<HelpingFor[]>('/trusted-helpers/helping-for', { signal }); }
export function renameTrustedHelper(id: string, alias: string): Promise<TrustedHelper> { return request<TrustedHelper>(`/trusted-helpers/${id}`, { method: 'PATCH', body: JSON.stringify({ alias }) }); }
export function revokeTrustedHelper(id: string): Promise<void> { return request<void>(`/trusted-helpers/${id}`, { method: 'DELETE' }); }
export function createPairing(method: Pairing['method']): Promise<Pairing> { return request<Pairing>('/pairings', { method: 'POST', body: JSON.stringify({ method }) }); }
export function getPairing(id: string, signal?: AbortSignal): Promise<PairingState> { return request<PairingState>(`/pairings/${id}`, { signal }); }
export function confirmPairing(id: string, alias?: string): Promise<TrustedHelper> { return request<TrustedHelper>(`/pairings/${id}/confirm`, { method: 'POST', body: JSON.stringify({ alias }) }); }
export function getPairingPreview(token: string, signal?: AbortSignal): Promise<PairingPreview> { return request<PairingPreview>(`/pairing-tokens/${token}`, { signal }); }
export function claimPairing(token: string): Promise<{ pairing_id: string; status: string }> { return request(`/pairing-tokens/${token}/claim`, { method: 'POST' }); }

export function getAssistInvite(token: string, signal?: AbortSignal): Promise<InvitePreview> {
  return request<InvitePreview>(`/assist-invites/${token}`, { signal });
}

export function acceptAssistInvite(token: string): Promise<InviteAcceptance> {
  return request<InviteAcceptance>(`/assist-invites/${token}/accept`, { method: 'POST' });
}

export function declineAssistInvite(token: string): Promise<{ help_callback_id: string; owner: { display_name: string } }> {
  return request(`/assist-invites/${token}/decline`, { method: 'POST' });
}

export function approveAssistParticipant(sessionId: string, participantId: string): Promise<AssistSession> {
  return request<AssistSession>(`/assist-sessions/${sessionId}/participants/${participantId}/approve`, { method: 'POST' });
}

export function rejectAssistParticipant(sessionId: string, participantId: string): Promise<AssistSession> {
  return request<AssistSession>(`/assist-sessions/${sessionId}/participants/${participantId}/reject`, { method: 'POST' });
}

export function leaveAssistSession(sessionId: string): Promise<void> {
  return request<void>(`/assist-sessions/${sessionId}/leave`, { method: 'POST' });
}

export function endAssistSession(sessionId: string): Promise<ConsultationSummary> {
  return request<ConsultationSummary>(`/assist-sessions/${sessionId}/end`, { method: 'POST' });
}
export function getVoiceToken(sessionId: string): Promise<VoiceToken> { return request<VoiceToken>(`/assist-sessions/${sessionId}/voice-token`, { method: 'POST' }); }
export function getPastHelp(serviceSessionId: string, signal?: AbortSignal): Promise<PastHelp> { return request<PastHelp>(`/service-sessions/${serviceSessionId}/past-help`, { signal }); }

export function getAssistSummary(sessionId: string, signal?: AbortSignal): Promise<ConsultationSummary> {
  return request<ConsultationSummary>(`/assist-sessions/${sessionId}/summary`, { signal });
}
export function getConsultations(as: 'owner' | 'helper', signal?: AbortSignal): Promise<ConsultationListItem[]> { return request<ConsultationListItem[]>(`/consultations?as=${as}&limit=20`, { signal }); }
export function getConsultation(id: string, signal?: AbortSignal): Promise<ConsultationDetail> { return request<ConsultationDetail>(`/consultations/${id}`, { signal }); }
export function getConsultationReplay(id: string, signal?: AbortSignal): Promise<ConsultationReplay> { return request<ConsultationReplay>(`/consultations/${id}/replay`, { signal }); }
export function deleteConsultationRecording(id: string): Promise<void> { return request<void>(`/consultations/${id}/recording`, { method: 'DELETE' }); }
export function getHelpCallbacks(as: 'owner' | 'helper', signal?: AbortSignal): Promise<HelpCallback[]> { return request<HelpCallback[]>(`/help-callbacks?as=${as}`, { signal }); }
export function markHelpCallbackReady(id: string): Promise<HelpCallback> { return request<HelpCallback>(`/help-callbacks/${id}/ready`, { method: 'POST' }); }
export function callHelpCallback(id: string): Promise<{ assist_session: AssistSession; invite: AssistInvite }> { return request(`/help-callbacks/${id}/call`, { method: 'POST' }); }
export function dismissHelpCallback(id: string): Promise<void> { return request<void>(`/help-callbacks/${id}`, { method: 'DELETE' }); }

export function getOperatorQueue(signal?: AbortSignal): Promise<OperatorQueueItem[]> { return request<OperatorQueueItem[]>('/operator/requests', { signal }); }
export function claimOperatorRequest(id: string): Promise<{ assist_session_id: string; participant_id: string }> { return request(`/operator/requests/${id}/claim`, { method: 'POST' }); }
export function requestOperatorForApplication(id: string, topic: OperatorQueueItem['topic']): Promise<{ assist_session: AssistSession; request: OperatorRequest }> { return request(`/service-sessions/${id}/operator-requests`, { method: 'POST', body: JSON.stringify({ topic }) }); }
