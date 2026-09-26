import { Button, CellList, CellSimple, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { claimOperatorRequest } from '../api/client';
import { operatorQueueQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';

const topics = { dont_understand: 'Не понимает, что выбрать', form_error: 'Ошибка в форме', other: 'Нужна помощь' };

export function O1OperatorQueue({ onClaim }: { onClaim: (assistId: string) => void }) {
  const queryClient = useQueryClient();
  const queue = useQuery({ queryKey: queryKeys.operatorQueue(), queryFn: operatorQueueQuery, refetchInterval: 5_000 });
  const claim = useMutation({ mutationFn: claimOperatorRequest, onSuccess: (result) => { void queryClient.invalidateQueries({ queryKey: queryKeys.operatorQueue() }); onClaim(result.assist_session_id); } });
  return <Flex direction="column" gap={12}>
    <ScreenIntro eyebrow="Сотрудник МФЦ" title="Очередь обращений" description="Возьмите обращение, чтобы подключиться к гражданину." />
    {queue.isLoading && <Typography.Text>Обновляем очередь…</Typography.Text>}
    {queue.error && <div className="notice notice--error">{queue.error instanceof Error ? queue.error.message : 'Не удалось загрузить очередь'}</div>}
    {queue.data?.length === 0 && <Typography.Text className="muted-text">Сейчас обращений нет.</Typography.Text>}
    <CellList mode="island" filled>{queue.data?.map((item) => <CellSimple key={item.id} surface="island" title={`${item.context.owner_display_name} · ${topics[item.topic]}`} subtitle={`${item.context.service_title}${item.context.step ? ` · шаг ${item.context.step.index}: ${item.context.step.title}` : ''}`} after={<Button size="small" variant="secondary" onClick={() => claim.mutate(item.id)} loading={claim.isPending}>Взять</Button>} />)}</CellList>
    {claim.error && <div className="notice notice--error">{claim.error instanceof Error ? claim.error.message : 'Не удалось взять обращение'}</div>}
  </Flex>;
}
