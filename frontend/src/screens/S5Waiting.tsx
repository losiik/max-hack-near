import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { AssistSession } from '../api/client';
import { ScreenIntro, StatusMark } from '../components/ScreenIntro';
import { ConfirmDialog } from '../components/AppDialog';
import { InlineAction } from '../components/InlineAction';
import { useState } from 'react';

interface S5WaitingProps {
  session: AssistSession;
  connection: string;
  operatorRequest?: { status: string; position: number | null } | null;
  onShareAgain: () => void;
  onContinue: () => void;
  onEnd: () => void;
}

export function S5Waiting({ session, connection, operatorRequest, onShareAgain, onContinue, onEnd }: S5WaitingProps) {
  const [confirmEnd, setConfirmEnd] = useState(false);
  const waitingForOperator = operatorRequest?.status === 'queued';
  return (
    <Flex direction="column" gap={12}>
      <ScreenIntro eyebrow="Помощь рядом" title={waitingForOperator ? 'Ждём специалиста' : 'Ждём помощника'} description={waitingForOperator ? 'Обращение передано в очередь МФЦ.' : 'Ссылка отправлена. Когда близкий подключится, вы сможете подтвердить его вход.'} />
      <div className="status-hero"><StatusMark tone={connection === 'reconnecting' ? 'attention' : 'positive'} /><div><Typography.Label>{connection === 'reconnecting' ? 'Соединение восстанавливается' : waitingForOperator ? `Вы в очереди${operatorRequest?.position ? `: ${operatorRequest.position}` : ''}` : 'Приглашение активно'}</Typography.Label><Typography.Text>{waitingForOperator ? 'Можно продолжать заполнять заявление — специалист подключится сам.' : 'Можно продолжать заполнять заявление.'}</Typography.Text></div></div>
      {!waitingForOperator && <InlineAction title="Пригласить ещё раз" description="Ссылка останется доступна, пока ждёте." action="Отправить" onClick={onShareAgain} />}
      <InlineAction title="Продолжить самому" description="Помощник сможет подключиться позже." action="Продолжить" variant="secondary" onClick={onContinue} />
      <InlineAction title="Отменить ожидание" description="Ссылка и запрос на помощь будут закрыты." action="Отменить" variant="destructive" onClick={() => setConfirmEnd(true)} />
      {confirmEnd && <ConfirmDialog title="Отменить ожидание?" description="Помощник больше не сможет подключиться по этой ссылке." confirmLabel="Отменить" destructive onCancel={() => setConfirmEnd(false)} onConfirm={onEnd} />}
    </Flex>
  );
}
