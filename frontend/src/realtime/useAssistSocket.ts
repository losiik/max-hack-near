import { useEffect } from 'react';
import { getAccessToken } from '../api/client';
import { useAssistStore, type AssistEnvelope } from './assistStore';

const ACK_COMMANDS = new Set([
  'annotation.highlight',
  'annotation.clear',
  'owner.flag_confusion',
]);

function websocketUrl(sessionId: string): string {
  const url = new URL(`/ws/assist/${sessionId}`, window.location.origin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.searchParams.set('token', getAccessToken());
  return url.toString();
}

export function useAssistSocket(sessionId: string | null): void {
  useEffect(() => {
    if (!sessionId || !getAccessToken()) return;
    let disposed = false;
    let socket: WebSocket | undefined;
    let pingTimer: number | undefined;
    let retryTimer: number | undefined;
    let attempts = 0;
    const store = useAssistStore;

    const cleanupSocket = () => {
      window.clearInterval(pingTimer);
      pingTimer = undefined;
      socket?.close();
      socket = undefined;
    };

    const connect = () => {
      if (disposed) return;
      store.getState().begin(sessionId);
      store.getState().setConnection(attempts ? 'reconnecting' : 'connecting');
      socket = new WebSocket(websocketUrl(sessionId));
      socket.onopen = () => {
        if (disposed) return;
        attempts = 0;
        store.getState().setConnection('connected');
        store.getState().setSender((command, payload) => {
          if (socket?.readyState !== WebSocket.OPEN) return null;
          const expectsAck = ACK_COMMANDS.has(command);
          const requestId = expectsAck ? crypto.randomUUID() : null;
          if (requestId) store.getState().setAnnotationFeedback({ state: 'sending', message: 'Показываем владельцу…', requestId });
          socket.send(JSON.stringify({ command, payload, ...(requestId ? { request_id: requestId } : {}) }));
          return requestId;
        });
        pingTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ command: 'presence.ping', payload: {} }));
        }, 20_000);
      };
      socket.onmessage = (event) => {
        try {
          store.getState().receive(JSON.parse(String(event.data)) as AssistEnvelope);
        } catch {
          store.getState().setConnection('error', 'Получено некорректное сообщение от сервера.');
        }
      };
      socket.onerror = () => {
        // A close event follows and determines whether reconnecting is appropriate.
      };
      socket.onclose = (event) => {
        window.clearInterval(pingTimer);
        store.getState().setSender(null);
        if (disposed) return;
        if (event.code === 4009) {
          store.getState().setConnection('closed');
          return;
        }
        if ([4001, 4003, 4004].includes(event.code)) {
          store.getState().setConnection('error', event.code === 4003 ? 'Нет доступа к этой встрече.' : 'Не удалось подключиться к встрече.');
          return;
        }
        const delay = event.code === 4029 ? 5_000 : [500, 1_000, 2_000, 5_000][Math.min(attempts, 3)];
        attempts += 1;
        store.getState().setConnection('reconnecting');
        retryTimer = window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      window.clearTimeout(retryTimer);
      cleanupSocket();
    };
  }, [sessionId]);
}
