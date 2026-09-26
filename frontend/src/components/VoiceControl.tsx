import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { Room } from 'livekit-client';
import { useEffect, useRef, useState } from 'react';
import { getVoiceToken } from '../api/client';

type VoiceStatus = 'idle' | 'connecting' | 'connected' | 'error';

export function VoiceControl({ sessionId }: { sessionId: string }) {
  const room = useRef<Room | null>(null);
  const [status, setStatus] = useState<VoiceStatus>('idle');
  const [muted, setMuted] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => () => { void room.current?.disconnect(); room.current = null; }, [sessionId]);

  async function connect() {
    if (status === 'connecting' || status === 'connected') return;
    setStatus('connecting'); setError('');
    try {
      const credentials = await getVoiceToken(sessionId);
      const { Room: LiveKitRoom, RoomEvent } = await import('livekit-client');
      const next = new LiveKitRoom({ adaptiveStream: true, dynacast: true });
      next.on(RoomEvent.ActiveSpeakersChanged, (speakers) => setSpeaking(speakers.some((speaker) => speaker.identity !== next.localParticipant.identity)));
      next.on(RoomEvent.Disconnected, () => { setStatus('idle'); setSpeaking(false); });
      await next.connect(credentials.url, credentials.token);
      await next.localParticipant.setMicrophoneEnabled(true);
      room.current = next;
      setMuted(false); setStatus('connected');
    } catch (reason) {
      await room.current?.disconnect(); room.current = null;
      setStatus('error'); setError(reason instanceof Error ? reason.message : 'Не удалось включить микрофон.');
    }
  }

  async function toggleMicrophone() {
    if (!room.current) return;
    try { await room.current.localParticipant.setMicrophoneEnabled(muted); setMuted(!muted); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось изменить состояние микрофона.'); }
  }

  if (status !== 'connected') return <Flex direction="column" gap={6}><Button size="small" stretched variant="secondary" disabled={status === 'connecting'} onClick={() => void connect()}>{status === 'connecting' ? 'Подключаем голос…' : 'Включить голос'}</Button>{error && <Typography.Text className="muted-text">{error}</Typography.Text>}</Flex>;
  return <Flex direction="column" gap={6} className="voice-control"><Button size="small" stretched variant={muted ? 'secondary' : 'primary'} onClick={() => void toggleMicrophone()}>{muted ? 'Включить микрофон' : 'Выключить микрофон'}</Button><Typography.Text className="muted-text">{speaking ? 'Собеседник говорит' : 'Голос подключён'}</Typography.Text></Flex>;
}
