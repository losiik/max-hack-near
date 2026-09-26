import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { assistSummaryQuery, queryKeys } from '../api/queries';
import { AppIcon, PersonRow, StatusScreen, Surface } from '../components/UiPrimitives';

export function S9Ended({ sessionId, owner, onContinue, onHome, onHistory }: { sessionId: string; owner: boolean; onContinue: () => void; onHome: () => void; onHistory: () => void }) {
  const summary = useQuery({ queryKey: queryKeys.assistSummary(sessionId), queryFn: assistSummaryQuery, retry: 1 });
  if (summary.isLoading) return <Typography.Text className="loading-copy">Готовим итог встречи…</Typography.Text>;
  const data = summary.data;
  const helpers = data?.helpers.map((item) => item.display_name).join(', ') || 'Помощник';
  return <div className="ui-page ended-screen"><StatusScreen icon="check" tone="green" title={owner ? 'Помощь завершена' : 'Консультация завершена'} /><Surface><PersonRow name={`Помогал: ${helpers}`} meta={data ? `Пройдено ${data.steps_completed ?? 0} из ${data.total_steps} шагов` : 'Встреча закончилась'} tone="blue" /><div className="consultation-summary"><span><AppIcon name="check" />Итоги встречи сохранены</span><span><AppIcon name="history" />Запись появится в истории помощи</span></div></Surface><Surface tone="blue" className="with-icon"><AppIcon name="history" /><p>Когда вы снова будете на этом шаге, можно будет вернуться к сохранённым подсказкам.</p></Surface><div className="screen-actions">{owner && data?.actions.can_continue && <Button size="small" stretched onClick={onContinue}>Продолжить оформление</Button>}<Button size="small" stretched variant="secondary" onClick={onHistory}>История помощи</Button><Button size="small" stretched variant="ghost" onClick={onHome}>На главную</Button></div></div>;
}
