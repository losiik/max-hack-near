import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { AssistSession } from '../api/client';
import { ScreenIntro, StatusMark } from '../components/ScreenIntro';

interface S5WaitingProps {
  session: AssistSession;
  connection: string;
  onShareAgain: () => void;
  onContinue: () => void;
  onEnd: () => void;
}

export function S5Waiting({ session, connection, onShareAgain, onContinue, onEnd }: S5WaitingProps) {
  return (
    <Flex direction="column" gap={12}>
      <ScreenIntro eyebrow="Помощь рядом" title="Ждём помощника" description="Ссылка отправлена. Когда близкий подключится, вы сможете подтвердить его вход." />
      <div className="status-hero"><StatusMark tone={connection === 'reconnecting' ? 'attention' : 'positive'} /><div><Typography.Label>{connection === 'reconnecting' ? 'Соединение восстанавливается' : 'Приглашение активно'}</Typography.Label><Typography.Text>Можно продолжать заполнять заявление.</Typography.Text></div></div>
      <Button size="small" stretched onClick={onShareAgain}>Отправить ссылку ещё раз</Button>
      <Button size="small" variant="secondary" stretched onClick={onContinue}>Продолжить заполнение</Button>
      <Button size="small" stretched variant="destructive" onClick={onEnd}>Отменить ожидание</Button>
    </Flex>
  );
}
