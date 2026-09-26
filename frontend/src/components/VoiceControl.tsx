import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useEffect, useRef } from 'react';
import { useVoiceRoom, type VoiceRole } from '../realtime/useVoiceRoom';
import { useToast } from './ToastProvider';

interface VoiceControlProps {
  sessionId: string;
  role: VoiceRole;
  autoConnect?: boolean;
}

export function VoiceControl({ sessionId, role, autoConnect = role === 'owner' }: VoiceControlProps) {
  const voice = useVoiceRoom({ sessionId, role, autoConnect });
  const previousRemote = useRef<string[]>([]);
  const toast = useToast();
  const remote = voice.remoteParticipants;
  const speaking = remote.find((participant) => participant.speaking);
  const muted = remote.find((participant) => !participant.microphoneEnabled);
  const remoteCopy = remote.length === 0
    ? role === 'owner' ? 'Помощник ещё не подключился к разговору' : 'Владелец ещё не в разговоре'
    : speaking ? `${speaking.displayName} говорит`
      : remote.length > 1 ? `В разговоре: ${remote.length}`
        : muted ? `Микрофон ${muted.displayName} выключен`
          : `${remote[0].displayName} в разговоре`;
  const localCopy = !voice.localMic
    ? 'Ваш микрофон выключен'
    : remote.length > 0
      ? role === 'helper' ? `${remote[0].displayName} слышит вас` : `${remote[0].displayName} вас слышит`
      : '';

  useEffect(() => {
    const current = remote.map((participant) => participant.identity);
    const joined = remote.find((participant) => !previousRemote.current.includes(participant.identity));
    const left = previousRemote.current.find((identity) => !current.includes(identity));
    if (joined) toast(`${remote.find((participant) => participant.identity === joined.identity)?.displayName ?? joined.identity} теперь в разговоре`);
    else if (left) toast('Участник больше не в разговоре');
    previousRemote.current = current;
  }, [remote, toast]);

  return (
    <section className="voice-control" aria-label="Голосовой разговор">
      {role === 'helper' && voice.connection === 'idle' && <Button size="small" stretched variant="primary" onClick={() => void voice.connect()}>Начать разговор</Button>}
      {voice.connection === 'connecting' && <Typography.Text className="muted-text">{role === 'owner' ? 'Подключаем звук…' : 'Подключаем разговор…'}</Typography.Text>}
      {voice.connection === 'idle' && role === 'owner' && autoConnect && <Typography.Text className="muted-text">Подключаем звук…</Typography.Text>}
      {voice.connection === 'reconnecting' && <Typography.Text className="muted-text">Восстанавливаем голосовое соединение…</Typography.Text>}
      {voice.connection === 'connected' && (
        <Flex direction="column" gap={6}>
          <Typography.Text className="voice-control__remote">{remoteCopy}</Typography.Text>
          <Flex align="center" gap={8} className="voice-control__actions">
            <Typography.Text className="muted-text">{localCopy}</Typography.Text>
            <Button size="small" variant={voice.localMic ? 'secondary' : 'primary'} onClick={() => void voice.toggleMicrophone()}>
              {voice.localMic ? 'Выключить микрофон' : 'Включить микрофон'}
            </Button>
          </Flex>
        </Flex>
      )}
      {voice.error && <Typography.Text className="notice--error">{voice.error}</Typography.Text>}
      {voice.connection === 'error' && <Button size="small" variant="secondary" onClick={() => void voice.connect()}>Повторить</Button>}
      {voice.connection === 'connected' && (voice.audioPlayback === 'blocked' || voice.audioPlayback === 'error') && (
        <div className="voice-control__playback">
          <Typography.Text>{voice.audioPlayback === 'blocked' ? 'Звук помощника готов' : 'Не удалось включить звук'}</Typography.Text>
          <Button size="small" variant="secondary" onClick={() => void voice.enableSound()}>Включить звук</Button>
        </div>
      )}
      <div ref={voice.audioContainerRef} className="voice-audio" aria-hidden="true" />
    </section>
  );
}
