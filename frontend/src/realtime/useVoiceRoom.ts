import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { getVoiceToken } from '../api/client';
import type { Room } from 'livekit-client';

export type VoiceRole = 'owner' | 'helper';
export type VoiceConnection = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error';
export type AudioPlayback = 'ready' | 'blocked' | 'error';

export interface VoiceRemoteParticipant {
  identity: string;
  displayName: string;
  connected: boolean;
  speaking: boolean;
  microphoneEnabled: boolean;
}

interface VoiceRoomOptions {
  sessionId: string;
  role: VoiceRole;
  autoConnect?: boolean;
}

export interface VoiceRoomState {
  connection: VoiceConnection;
  localMic: boolean;
  remoteParticipants: VoiceRemoteParticipant[];
  audioPlayback: AudioPlayback;
  error: string;
  audioContainerRef: RefObject<HTMLDivElement | null>;
  connect: () => Promise<void>;
  toggleMicrophone: () => Promise<void>;
  enableSound: () => Promise<void>;
}

function microphoneError(reason: unknown): string {
  if (isMicrophonePermissionError(reason)) {
    const inMax = typeof window !== 'undefined' && Boolean(window.WebApp?.initData);
    return inMax ? 'MAX не дал доступ к микрофону. Разрешите микрофон и попробуйте снова.' : 'Нет доступа к микрофону. Разрешите доступ и попробуйте снова.';
  }
  return 'Не удалось подключить микрофон.';
}

function isMicrophonePermissionError(reason: unknown): boolean {
  const name = typeof DOMException !== 'undefined' && reason instanceof DOMException ? reason.name : '';
  const message = reason instanceof Error ? reason.message.toLowerCase() : '';
  return name === 'NotAllowedError'
    || name === 'PermissionDeniedError'
    || name === 'NotReadableError'
    || message.includes('permission')
    || message.includes('not allowed')
    || message.includes('microphone');
}

function voiceConnectionError(): string {
  return 'Не удалось подключить голос. Попробуйте ещё раз.';
}

export function useVoiceRoom({ sessionId, role, autoConnect = false }: VoiceRoomOptions): VoiceRoomState {
  const roomRef = useRef<Room | null>(null);
  const disposedRef = useRef(false);
  const intentionalDisconnectRef = useRef(false);
  const shouldReconnectRef = useRef(autoConnect);
  const connectingRef = useRef(false);
  const reconnectTimerRef = useRef<number | undefined>(undefined);
  const reconnectAttemptsRef = useRef(0);
  const connectedOnceRef = useRef(false);
  const desiredMicEnabledRef = useRef(false);
  const localMicRef = useRef(false);
  const connectRef = useRef<(() => Promise<void>) | undefined>(undefined);
  const audioContainerRef = useRef<HTMLDivElement | null>(null);
  const audioTracksRef = useRef(new Map<string, Set<HTMLMediaElement>>());
  const audioTrackKeysRef = useRef(new Set<string>());
  const [connection, setConnection] = useState<VoiceConnection>('idle');
  const [localMic, setLocalMic] = useState(false);
  const [remoteParticipants, setRemoteParticipants] = useState<VoiceRemoteParticipant[]>([]);
  const [audioPlayback, setAudioPlayback] = useState<AudioPlayback>('ready');
  const [error, setError] = useState('');

  const updateRemote = useCallback((identity: string, displayName: string, speaking: boolean, microphoneEnabled: boolean) => {
    setRemoteParticipants((current) => {
      const existing = current.find((item) => item.identity === identity);
      if (existing && existing.displayName === (displayName || identity) && existing.connected && existing.speaking === speaking && existing.microphoneEnabled === microphoneEnabled) return current;
      const next = current.filter((item) => item.identity !== identity);
      return [...next, { identity, displayName: displayName || identity, connected: true, speaking, microphoneEnabled }];
    });
  }, []);

  const updateRemoteMicrophone = useCallback((identity: string, microphoneEnabled: boolean) => {
    setRemoteParticipants((current) => current.map((participant) => participant.identity === identity ? { ...participant, microphoneEnabled } : participant));
  }, []);

  const removeRemote = useCallback((identity: string) => {
    setRemoteParticipants((current) => current.filter((item) => item.identity !== identity));
    const elements = audioTracksRef.current.get(identity);
    elements?.forEach((element) => element.remove());
    audioTracksRef.current.delete(identity);
    [...audioTrackKeysRef.current].filter((key) => key.startsWith(`${identity}:`)).forEach((key) => audioTrackKeysRef.current.delete(key));
  }, []);

  const clearAudio = useCallback(() => {
    audioTracksRef.current.forEach((elements) => elements.forEach((element) => element.remove()));
    audioTracksRef.current.clear();
    audioTrackKeysRef.current.clear();
    if (audioContainerRef.current) audioContainerRef.current.replaceChildren();
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== undefined) window.clearTimeout(reconnectTimerRef.current);
    reconnectTimerRef.current = undefined;
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (disposedRef.current || intentionalDisconnectRef.current || !shouldReconnectRef.current || reconnectTimerRef.current !== undefined) return;
    const delay = [500, 1_000, 2_000, 5_000][Math.min(reconnectAttemptsRef.current, 3)];
    reconnectAttemptsRef.current += 1;
    setConnection('reconnecting');
    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = undefined;
      void connectRef.current?.();
    }, delay);
  }, []);

  const detachAudioTrack = useCallback((track: { detach: () => HTMLMediaElement[] }, identity: string, trackSid?: string) => {
    track.detach().forEach((element) => element.remove());
    const elements = audioTracksRef.current.get(identity);
    elements?.forEach((element) => { if (!element.isConnected) elements.delete(element); });
    if (elements && elements.size === 0) audioTracksRef.current.delete(identity);
    if (trackSid) audioTrackKeysRef.current.delete(`${identity}:${trackSid}`);
  }, []);

  const attachAudio = useCallback((track: { kind: string; attach: () => HTMLMediaElement }, identity: string, trackSid: string) => {
    if (track.kind !== 'audio' || audioTrackKeysRef.current.has(`${identity}:${trackSid}`)) return;
    const element = track.attach();
    element.autoplay = true;
    element.setAttribute('playsinline', 'true');
    element.setAttribute('aria-hidden', 'true');
    element.classList.add('voice-audio__track');
    audioContainerRef.current?.appendChild(element);
    const elements = audioTracksRef.current.get(identity) ?? new Set<HTMLMediaElement>();
    elements.add(element);
    audioTracksRef.current.set(identity, elements);
    audioTrackKeysRef.current.add(`${identity}:${trackSid}`);
    void element.play().catch(() => setAudioPlayback('blocked'));
  }, []);

  const disconnectRoom = useCallback(async () => {
    intentionalDisconnectRef.current = true;
    shouldReconnectRef.current = false;
    clearReconnectTimer();
    const room = roomRef.current;
    roomRef.current = null;
    clearAudio();
    setRemoteParticipants([]);
    localMicRef.current = false;
    setLocalMic(false);
    if (room) await room.disconnect();
  }, [clearAudio, clearReconnectTimer]);

  const connectInternal = useCallback(async () => {
    if (disposedRef.current || connectingRef.current || roomRef.current || !shouldReconnectRef.current) return;
    connectingRef.current = true;
    setConnection(reconnectAttemptsRef.current > 0 ? 'reconnecting' : 'connecting');
    setError('');
    try {
      const credentials = await getVoiceToken(sessionId);
      const { Room: LiveKitRoom, RoomEvent, Track } = await import('livekit-client');
      if (disposedRef.current || intentionalDisconnectRef.current || !shouldReconnectRef.current) return;
      const room = new LiveKitRoom({ adaptiveStream: true, dynacast: true });
      roomRef.current = room;
      const microphoneEnabled = (participant: { getTrackPublication: (source: typeof Track.Source.Microphone) => { isMuted: boolean } | undefined }) => {
        const publication = participant.getTrackPublication(Track.Source.Microphone);
        return Boolean(publication && !publication.isMuted);
      };
      const participantSpeaking = (identity: string) => room.activeSpeakers.some((speaker) => speaker.identity === identity);
      const refreshSpeakers = (speakers: Array<{ identity: string }>) => {
        const active = new Set(speakers.map((speaker) => speaker.identity));
        setRemoteParticipants((current) => current.map((participant) => ({ ...participant, speaking: active.has(participant.identity) })));
      };

      room.on(RoomEvent.ParticipantConnected, (participant) => updateRemote(participant.identity, participant.name ?? participant.identity, participantSpeaking(participant.identity), microphoneEnabled(participant)));
      room.on(RoomEvent.ParticipantDisconnected, (participant) => removeRemote(participant.identity));
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => refreshSpeakers(speakers));
      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (publication.source === Track.Source.Microphone) updateRemote(participant.identity, participant.name ?? participant.identity, participantSpeaking(participant.identity), !publication.isMuted);
        attachAudio(track, participant.identity, publication.trackSid);
      });
      room.on(RoomEvent.TrackUnsubscribed, (track, publication, participant) => detachAudioTrack(track, participant.identity, publication.trackSid));
      room.on(RoomEvent.TrackMuted, (publication, participant) => {
        if (publication.source === Track.Source.Microphone && participant.identity !== room.localParticipant.identity) updateRemoteMicrophone(participant.identity, false);
      });
      room.on(RoomEvent.TrackUnmuted, (publication, participant) => {
        if (publication.source === Track.Source.Microphone && participant.identity !== room.localParticipant.identity) updateRemoteMicrophone(participant.identity, true);
      });
      room.on(RoomEvent.Reconnecting, () => setConnection('reconnecting'));
      room.on(RoomEvent.SignalReconnecting, () => setConnection('reconnecting'));
      room.on(RoomEvent.Reconnected, () => { reconnectAttemptsRef.current = 0; setConnection('connected'); setError(''); });
      room.on(RoomEvent.AudioPlaybackStatusChanged, (playing) => setAudioPlayback(playing ? 'ready' : 'blocked'));
      room.on(RoomEvent.Disconnected, () => {
        if (roomRef.current !== room) return;
        roomRef.current = null;
        clearAudio();
        setRemoteParticipants([]);
        localMicRef.current = false;
        setLocalMic(false);
        if (!disposedRef.current && !intentionalDisconnectRef.current && shouldReconnectRef.current) scheduleReconnect();
        else if (!disposedRef.current) setConnection('idle');
      });

      await room.connect(credentials.url, credentials.token);
      if (roomRef.current !== room) return;
      if (disposedRef.current || intentionalDisconnectRef.current || !shouldReconnectRef.current) {
        roomRef.current = null;
        await room.disconnect();
        return;
      }
      for (const participant of room.remoteParticipants.values()) {
        updateRemote(participant.identity, participant.name ?? participant.identity, participantSpeaking(participant.identity), microphoneEnabled(participant));
        participant.trackPublications.forEach((publication) => {
          if (publication.source === Track.Source.Microphone && publication.track) attachAudio(publication.track, participant.identity, publication.trackSid);
        });
      }
      try {
        await room.startAudio();
        setAudioPlayback('ready');
      } catch {
        setAudioPlayback('blocked');
      }
      const wantedMic = desiredMicEnabledRef.current;
      if (wantedMic) await room.localParticipant.setMicrophoneEnabled(true);
      localMicRef.current = wantedMic;
      setLocalMic(localMicRef.current);
      connectedOnceRef.current = true;
      reconnectAttemptsRef.current = 0;
      setConnection('connected');
      setError('');
    } catch (reason) {
      const room = roomRef.current;
      if (room) {
        roomRef.current = null;
        await room.disconnect().catch(() => undefined);
      }
      clearAudio();
      setRemoteParticipants([]);
      localMicRef.current = false;
      setLocalMic(false);
      if (!disposedRef.current && shouldReconnectRef.current && connectedOnceRef.current && !isMicrophonePermissionError(reason)) {
        setError(voiceConnectionError());
        scheduleReconnect();
      } else if (!disposedRef.current) {
        setConnection('error');
        setError(isMicrophonePermissionError(reason) ? microphoneError(reason) : voiceConnectionError());
      }
    } finally {
      connectingRef.current = false;
    }
  }, [attachAudio, clearAudio, detachAudioTrack, removeRemote, role, scheduleReconnect, sessionId, updateRemote, updateRemoteMicrophone]);

  connectRef.current = connectInternal;

  const connect = useCallback(async () => {
    shouldReconnectRef.current = true;
    intentionalDisconnectRef.current = false;
    if (role === 'helper') desiredMicEnabledRef.current = true;
    await connectInternal();
  }, [connectInternal, role]);

  const toggleMicrophone = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;
    const next = !localMicRef.current;
    try {
      await room.localParticipant.setMicrophoneEnabled(next);
      desiredMicEnabledRef.current = next;
      localMicRef.current = next;
      setLocalMic(next);
      setError('');
    } catch (reason) {
      setError(microphoneError(reason));
    }
  }, []);

  const enableSound = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;
    try {
      await room.startAudio();
      const elements = [...audioTracksRef.current.values()].flatMap((items) => [...items]);
      await Promise.all(elements.map((element) => element.play()));
      setAudioPlayback('ready');
      setError('');
    } catch {
      setAudioPlayback('error');
      setError('Не удалось включить звук. Разрешите воспроизведение и попробуйте снова.');
    }
  }, []);

  useEffect(() => {
    disposedRef.current = false;
    intentionalDisconnectRef.current = false;
    shouldReconnectRef.current = autoConnect;
    reconnectAttemptsRef.current = 0;
    connectedOnceRef.current = false;
    desiredMicEnabledRef.current = false;
    if (autoConnect) void connectInternal();
    return () => {
      disposedRef.current = true;
      void disconnectRoom();
    };
  }, [autoConnect, connectInternal, disconnectRoom, sessionId]);

  return { connection, localMic, remoteParticipants, audioPlayback, error, audioContainerRef, connect, toggleMicrophone, enableSound };
}
