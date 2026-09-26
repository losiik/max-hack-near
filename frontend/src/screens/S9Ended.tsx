import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { assistSummaryQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';

export function S9Ended({ sessionId, owner, onContinue, onHome, onHistory }: { sessionId: string; owner: boolean; onContinue: () => void; onHome: () => void; onHistory: () => void }) {
  const summary = useQuery({ queryKey: queryKeys.assistSummary(sessionId), queryFn: assistSummaryQuery, retry: 1 });
  if (summary.isLoading) return <Typography.Text className="loading-copy">Готовим итог встречи…</Typography.Text>;
  const data = summary.data;
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title={owner ? 'Помощь завершена' : 'Консультация завершена'} description={data ? `Помогал: ${data.helpers.map((item) => item.display_name).join(', ') || 'помощник'}` : 'Встреча закончилась.'} meta={data ? `Пройдено ${data.steps_completed ?? 0} из ${data.total_steps} шагов` : undefined} />{owner && data?.actions.can_continue && <Button size="small" stretched onClick={onContinue}>Продолжить оформление</Button>}<Button size="small" stretched variant="secondary" onClick={onHistory}>История консультаций</Button><Button size="small" stretched variant="ghost" onClick={onHome}>На главную</Button></Flex>;
}
