import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { claimOperatorRequest } from '../api/client';
import { operatorQueueQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { AppIcon, Surface } from '../components/UiPrimitives';

const topics = { dont_understand: 'Не понимает, что выбрать', form_error: 'Ошибка в форме', other: 'Нужна помощь' };

export function O1OperatorQueue({ onClaim }: { onClaim: (assistId: string) => void }) {
  const queryClient = useQueryClient();
  const queue = useQuery({ queryKey: queryKeys.operatorQueue(), queryFn: operatorQueueQuery, refetchInterval: 5_000 });
  const claim = useMutation({ mutationFn: claimOperatorRequest, onSuccess: (result) => { void queryClient.invalidateQueries({ queryKey: queryKeys.operatorQueue() }); onClaim(result.assist_session_id); } });
  return <div className="ui-page operator-queue-screen">
    <ScreenIntro title="Очередь обращений" description="Возьмите обращение, чтобы подключиться к гражданину." />
    <div className="staff-badge"><AppIcon name="shield" />Сотрудник МФЦ · подтверждённый профиль</div>
    <div className="queue-count">Ждут помощи: {queue.data?.length ?? 0}</div>
    {queue.isLoading && <Typography.Text>Обновляем очередь…</Typography.Text>}
    {queue.error && <div className="notice notice--error">{queue.error instanceof Error ? queue.error.message : 'Не удалось загрузить очередь'}</div>}
    {queue.data?.length === 0 && <Typography.Text className="muted-text">Сейчас обращений нет.</Typography.Text>}
    {queue.data?.map((item, index) => <Surface className="queue-card" key={item.id}><div className="queue-card__head"><strong>{item.context.owner_display_name}</strong><span><AppIcon name="clock" />{item.waiting_sec < 60 ? `${item.waiting_sec} с` : `${Math.round(item.waiting_sec / 60)} мин`}</span></div><p>{item.context.service_title}{item.context.step ? ` · шаг ${item.context.step.index} из ${item.context.step.total} «${item.context.step.title}»` : ''}</p><div className="ui-chips"><span className="is-warning">{topics[item.topic]}</span>{item.context.error_codes.map((code) => <span key={code}>{code.replaceAll('_', ' ')}</span>)}</div>{item.context.ai_summary && <div className="ai-summary"><strong><AppIcon name="robot" />Что рассказал цифровой сотрудник</strong><p>{item.context.ai_summary}</p></div>}<Button size="small" stretched variant={index === 0 ? 'primary' : 'secondary'} onClick={() => claim.mutate(item.id)} loading={claim.isPending}>Взять в работу</Button></Surface>)}
    {claim.error && <div className="notice notice--error">{claim.error instanceof Error ? claim.error.message : 'Не удалось взять обращение'}</div>}
  </div>;
}
