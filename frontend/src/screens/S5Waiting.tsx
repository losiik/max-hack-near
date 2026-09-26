import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { AssistSession } from '../api/client';
import { ScreenIntro, StatusMark } from '../components/ScreenIntro';

interface S5WaitingProps {
  session: AssistSession;
  connection: string;
  operatorRequest?: { status: string; position: number | null } | null;
  onShareAgain: () => void;
  onContinue: () => void;
  onEnd: () => void;
}

export function S5Waiting({ session, connection, operatorRequest, onShareAgain, onContinue, onEnd }: S5WaitingProps) {
  const waitingForOperator = operatorRequest?.status === 'queued';
  return (
    <Flex direction="column" gap={12}>
      <ScreenIntro eyebrow="Помощь рядом" title={waitingForOperator ? 'Ждём специалиста' : 'Ждём помощника'} description={waitingForOperator ? 'Обращение передано в очередь МФЦ.' : 'Ссылка отправлена. Когда близкий подключится, вы сможете подтвердить его вход.'} />
      <div className="status-hero"><StatusMark tone={connection === 'reconnecting' ? 'attention' : 'positive'} /><div><Typography.Label>{connection === 'reconnecting' ? 'Соединение восстанавливается' : waitingForOperator ? `Вы в очереди${operatorRequest?.position ? `: ${operatorRequest.position}` : ''}` : 'Приглашение активно'}</Typography.Label><Typography.Text>{waitingForOperator ? 'Можно продолжать заполнять заявление — специалист подключится сам.' : 'Можно продолжать заполнять заявление.'}</Typography.Text></div></div>
      {!waitingForOperator && <Button size="small" stretched onClick={onShareAgain}>Отправить ссылку ещё раз</Button>}
      <Button size="small" variant="secondary" stretched onClick={onContinue}>Продолжить заполнение</Button>
      <Button size="small" stretched variant="destructive" onClick={onEnd}>Отменить ожидание</Button>
    </Flex>
  );
}
