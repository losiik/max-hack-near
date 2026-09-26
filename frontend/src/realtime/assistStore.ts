import { create } from 'zustand';
import type { AssistParticipant, FieldError, ProjectedState } from '../api/client';

export type AssistConnection = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'closed' | 'error';

export interface AssistEnvelope {
  event: string;
  session_id?: string;
  seq: number | null;
  payload: Record<string, unknown>;
}

interface PendingAssist {
  participant_id: string;
  owner: { display_name: string };
  service: { title: string };
}

interface JoinRequest {
  id: string;
  display_name: string;
  photo_url: string | null;
  role: string;
  max_username?: string | null;
}

export interface AssistPointer {
  elementId: string;
  relX: number;
  relY: number;
}

export interface AssistSelectView { elementId: string; scrollTop: number; viewportHeight?: number }

export interface AnnotationFeedback { state: 'sending' | 'sent' | 'error'; message: string; requestId: string; }

interface AssistRealtimeState {
  sessionId: string | null;
  connection: AssistConnection;
  snapshot: ProjectedState | null;
  pending: PendingAssist | null;
  joinRequest: JoinRequest | null;
  endedReason: string | null;
  pointer: AssistPointer | null;
  confusionElementId: string | null;
  selectView: AssistSelectView | null;
  inviteDeclined: boolean;
  rejected: boolean;
  annotationFeedback: AnnotationFeedback | null;
  lastSeq: number;
  error: string | null;
  sendCommand: ((command: string, payload: Record<string, unknown>) => string | null) | null;
  begin: (sessionId: string) => void;
  setConnection: (connection: AssistConnection, error?: string | null) => void;
  setSender: (sender: AssistRealtimeState['sendCommand']) => void;
  setAnnotationFeedback: (feedback: AnnotationFeedback | null) => void;
  setSelectView: (view: AssistSelectView | null) => void;
  receive: (message: AssistEnvelope) => void;
  clearJoinRequest: () => void;
  reset: () => void;
}

function withParticipant(snapshot: ProjectedState, participant: AssistParticipant): ProjectedState {
  const participants = [...snapshot.session.participants.filter((item) => item.id !== participant.id), participant];
  return { ...snapshot, session: { ...snapshot.session, participants } };
}

export const useAssistStore = create<AssistRealtimeState>((set, get) => ({
  sessionId: null,
  connection: 'idle',
  snapshot: null,
  pending: null,
  joinRequest: null,
  endedReason: null,
  pointer: null,
  confusionElementId: null,
  selectView: null,
  inviteDeclined: false,
  rejected: false,
  annotationFeedback: null,
  lastSeq: 0,
  error: null,
  sendCommand: null,
  begin: (sessionId) => {
    if (get().sessionId === sessionId) return;
    set({ sessionId, connection: 'connecting', snapshot: null, pending: null, joinRequest: null, endedReason: null, pointer: null, confusionElementId: null, selectView: null, inviteDeclined: false, rejected: false, annotationFeedback: null, lastSeq: 0, error: null, sendCommand: null });
  },
  setConnection: (connection, error = null) => set({ connection, error }),
  setSender: (sendCommand) => set({ sendCommand }),
  setAnnotationFeedback: (annotationFeedback) => set({ annotationFeedback }),
  setSelectView: (selectView) => set({ selectView }),
  clearJoinRequest: () => set({ joinRequest: null }),
  reset: () => set({ sessionId: null, connection: 'idle', snapshot: null, pending: null, joinRequest: null, endedReason: null, pointer: null, confusionElementId: null, selectView: null, inviteDeclined: false, rejected: false, annotationFeedback: null, lastSeq: 0, error: null, sendCommand: null }),
  receive: (message) => {
    const state = get();
    if (message.session_id && state.sessionId && message.session_id !== state.sessionId) return;
    if (message.seq !== null && message.event !== 'session.snapshot' && message.seq <= state.lastSeq) return;

    if (message.event === 'session.snapshot') {
      const snapshot = message.payload as unknown as ProjectedState;
      const rawSelectView = (message.payload.select_view ?? null) as {
        element_id?: unknown;
        scroll_top?: unknown;
        viewport_height?: unknown;
      } | null;
      const selectView = typeof rawSelectView?.element_id === 'string'
        ? {
          elementId: rawSelectView.element_id,
          scrollTop: Math.max(0, Number(rawSelectView.scroll_top) || 0),
          viewportHeight: Math.max(0, Number(rawSelectView.viewport_height) || 0) || undefined,
        }
        : null;
      set({ snapshot, selectView, pending: null, rejected: false, lastSeq: snapshot.last_seq, connection: 'connected', error: null });
      return;
    }
    if (message.event === 'session.pending') {
      set({ pending: message.payload as unknown as PendingAssist, snapshot: null, connection: 'connected', error: null });
      return;
    }

    const nextSeq = message.seq === null ? state.lastSeq : message.seq;
    const snapshot = state.snapshot;
    if (message.event === 'ack') {
      const requestId = String(message.payload.request_id ?? '');
      if (state.annotationFeedback?.requestId === requestId) set({ annotationFeedback: { state: 'sent', message: 'Пометка отправлена', requestId } });
      return;
    }
    if (message.event === 'error') {
      const requestId = String(message.payload.request_id ?? '');
      if (state.annotationFeedback?.requestId === requestId) set({ annotationFeedback: { state: 'error', message: String(message.payload.message ?? 'Не удалось показать пометку'), requestId } });
      return;
    }
    if (message.event === 'session.ended') {
      set({ endedReason: String(message.payload.reason ?? 'ended'), connection: 'closed', selectView: null, lastSeq: nextSeq });
      return;
    }
    if (message.event === 'invite.declined') {
      set({ inviteDeclined: true, lastSeq: nextSeq });
      return;
    }
    if (message.event === 'participant.join_requested') {
      const participant = message.payload.participant as JoinRequest | undefined;
      set({ joinRequest: participant ?? null, lastSeq: nextSeq });
      return;
    }
    if (message.event === 'session.activated') {
      const startedAt = typeof message.payload.started_at === 'string' ? message.payload.started_at : undefined;
      set({
        snapshot: snapshot
          ? { ...snapshot, session: { ...snapshot.session, status: 'active', ...(startedAt ? { started_at: startedAt } : {}) } }
          : snapshot,
        pending: null,
        rejected: false,
        lastSeq: nextSeq,
      });
      return;
    }
    if (message.event === 'form.select_view') {
      const elementId = message.payload.element_id;
      set({
        selectView: message.payload.open === true && typeof elementId === 'string'
          ? {
            elementId,
            scrollTop: Math.max(0, Number(message.payload.scroll_top) || 0),
            viewportHeight: Math.max(0, Number(message.payload.viewport_height) || 0) || undefined,
          }
          : null,
      });
      return;
    }
    if (message.event === 'participant.status_changed' && state.pending) {
      const status = String(message.payload.status ?? '');
      if (status === 'rejected') {
        set({ pending: null, rejected: true, lastSeq: nextSeq });
        return;
      }
      if (status === 'active') {
        set({ pending: null, lastSeq: nextSeq });
        return;
      }
    }
    if (!snapshot) {
      set({ lastSeq: nextSeq });
      return;
    }

    if (message.event === 'participant.joined') {
      const participant = message.payload.participant as AssistParticipant | undefined;
      if (participant) set({ snapshot: withParticipant(snapshot, participant), lastSeq: nextSeq });
      return;
    }
    if (message.event === 'participant.left') {
      const id = String(message.payload.participant_id ?? '');
      set({
        snapshot: { ...snapshot, session: { ...snapshot.session, participants: snapshot.session.participants.filter((item) => item.id !== id) } },
        lastSeq: nextSeq,
      });
      return;
    }
    if (message.event === 'presence.changed') {
      const id = String(message.payload.participant_id ?? '');
      const online = Boolean(message.payload.online);
      set({
        snapshot: {
          ...snapshot,
          session: {
            ...snapshot.session,
            participants: snapshot.session.participants.map((item) => (item.id === id ? { ...item, online } : item)),
          },
        },
        lastSeq: nextSeq,
      });
      return;
    }
    if (message.event === 'participant.status_changed') {
      const id = String(message.payload.participant_id ?? '');
      const status = String(message.payload.status ?? '');
      set({
        pending: status === 'active' ? null : state.pending,
        snapshot: {
          ...snapshot,
          session: {
            ...snapshot.session,
            me: snapshot.session.me.participant_id === id ? { ...snapshot.session.me, status } : snapshot.session.me,
            participants: snapshot.session.participants.map((item) => (item.id === id ? { ...item, status } : item)),
          },
        },
        lastSeq: nextSeq,
      });
      return;
    }
    if (message.event === 'navigation.step_changed' || message.event === 'form.field_updated') {
      const currentStep = message.payload.current_step as ProjectedState['current_step'] | undefined;
      const errors = (message.payload.errors as FieldError[] | undefined) ?? snapshot.errors;
      const steps = (message.payload.steps as ProjectedState['steps'] | undefined) ?? snapshot.steps;
      set({ snapshot: { ...snapshot, current_step: currentStep ?? snapshot.current_step, errors, steps, annotations: message.event === 'navigation.step_changed' ? [] : snapshot.annotations }, pointer: message.event === 'navigation.step_changed' ? null : state.pointer, confusionElementId: message.event === 'navigation.step_changed' ? null : state.confusionElementId, selectView: message.event === 'navigation.step_changed' ? null : state.selectView, lastSeq: nextSeq });
      return;
    }
    if (message.event === 'form.validation_failed') {
      set({ snapshot: { ...snapshot, errors: (message.payload.errors as FieldError[] | undefined) ?? snapshot.errors }, lastSeq: nextSeq });
      return;
    }
    if (message.event === 'recording.status_changed') {
      const status = String(message.payload.status ?? '');
      set({ snapshot: { ...snapshot, session: { ...snapshot.session, recording: snapshot.session.recording ? { ...snapshot.session.recording, status } : { status, duration_ms: null } } }, lastSeq: nextSeq });
      return;
    }
    if (message.event === 'annotation.created') {
      const annotation = message.payload as unknown as ProjectedState['annotations'][number];
      set({ snapshot: { ...snapshot, annotations: [...snapshot.annotations.filter((item) => item.id !== annotation.id), annotation] }, lastSeq: nextSeq });
      return;
    }
    if (message.event === 'annotation.cleared') {
      const ids = new Set((message.payload.annotation_ids as string[] | undefined) ?? []);
      set({ snapshot: { ...snapshot, annotations: snapshot.annotations.filter((item) => !ids.has(item.id)) }, lastSeq: nextSeq });
      return;
    }
    if (message.event === 'annotation.pointer') {
      if (message.payload.visible === false) {
        set({ pointer: null, lastSeq: nextSeq });
      } else {
        set({ pointer: { elementId: String(message.payload.element_id), relX: Number(message.payload.rel_x), relY: Number(message.payload.rel_y) }, lastSeq: nextSeq });
      }
      return;
    }
    if (message.event === 'owner.confusion_flagged') {
      set({ confusionElementId: String(message.payload.element_id ?? ''), lastSeq: nextSeq });
      return;
    }
    set({ lastSeq: nextSeq });
  },
}));
