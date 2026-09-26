import { Button } from '@maxhub/max-ui';
import type { AssistSession } from '../api/client';
import { StatusMark } from '../components/ScreenIntro';
import { ConfirmDialog } from '../components/AppDialog';
import { useState } from 'react';
import { AppIcon, StatusScreen, Surface } from '../components/UiPrimitives';

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
    <div className="ui-page waiting-screen">
      <Surface><StatusScreen icon={waitingForOperator ? 'headset' : 'link'} title={waitingForOperator ? 'Ждём специалиста' : 'Приглашение отправлено'} description={waitingForOperator ? 'Обращение передано в очередь МФЦ. Специалист подключится, когда освободится.' : 'Когда близкий подключится, вы услышите его голос и сможете подтвердить вход.'}><div className="status-meta"><StatusMark tone={connection === 'reconnecting' ? 'attention' : 'positive'} /><span>{connection === 'reconnecting' ? 'Соединение восстанавливается' : waitingForOperator ? `Вы в очереди${operatorRequest?.position ? `: ${operatorRequest.position}` : ''}` : 'Приглашение активно'}</span></div></StatusScreen></Surface>
      <Surface tone="blue" className="with-icon"><AppIcon name="info" /><p>Пока ждёте, можно продолжать заполнять — черновик сохраняется сам.</p></Surface>
      <div className="screen-actions">
        {!waitingForOperator && <Button size="small" stretched onClick={onShareAgain}><AppIcon name="link" />Отправить ссылку ещё раз</Button>}
        <Button size="small" stretched variant="secondary" onClick={onContinue}>Вернуться к заявлению</Button>
        <Button size="small" stretched variant="destructive" onClick={() => setConfirmEnd(true)}>Отменить ожидание</Button>
      </div>
      {confirmEnd && <ConfirmDialog title="Отменить ожидание?" description="Помощник больше не сможет подключиться по этой ссылке." confirmLabel="Отменить" destructive onCancel={() => setConfirmEnd(false)} onConfirm={onEnd} />}
    </div>
  );
}
