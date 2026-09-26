import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { consultationsQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { AppIcon, formatDate, formatDuration, PersonRow, SegmentedControl } from '../components/UiPrimitives';

export function R1Consultations({ as: initialRole, onOpen }: { as: 'owner' | 'helper'; onOpen: (id: string) => void }) {
  const [as, setAs] = useState(initialRole);
  const list = useQuery({
    queryKey: queryKeys.consultations(as),
    queryFn: consultationsQuery,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => query.state.data?.some((item) => item.recording?.status === 'recording') ? 3000 : false,
  });
  return <div className="ui-page consultations-screen"><ScreenIntro title="История помощи" /><SegmentedControl value={as} options={[{ value: 'owner', label: 'Мне помогали' }, { value: 'helper', label: 'Я помогал' }]} onChange={setAs} />{list.isLoading && <Typography.Text>Загружаем историю…</Typography.Text>}{list.error && <div className="notice notice--error" role="alert"><Flex direction="column" gap={8}><Typography.Text>{list.error instanceof Error ? list.error.message : 'Не удалось загрузить историю'}</Typography.Text><Button size="small" onClick={() => void list.refetch()}>Повторить</Button></Flex></div>}{list.data?.length === 0 && <Typography.Text className="muted-text">Консультаций пока нет.</Typography.Text>}<div className="consultation-list">{list.data?.map((item) => { const helper = item.helpers[0]; const person = as === 'owner' ? item.helpers.map((entry) => entry.display_name).join(', ') || 'Помощник' : item.owner_display_name || 'Владелец'; const tone = helper?.role === 'ai_agent' ? 'agent' : helper?.badge?.verified ? 'purple' : 'blue'; return <button type="button" className="consultation-card" key={item.assist_session_id} onClick={() => onOpen(item.assist_session_id)}><div className="consultation-card__head"><strong>{item.service.title}</strong><span>{formatDate(item.ended_at)}</span></div><PersonRow name={person} meta={`${formatDuration(item.duration_sec)} · ${item.recording?.status === 'ready' ? 'есть запись' : 'без записи'}`} tone={tone} trailing={item.recording?.status === 'ready' ? <AppIcon name="play" /> : <AppIcon name="chevron" />} /><div className="consultation-card__steps"><AppIcon name="check" />Пройдено {item.steps_completed ?? 0} из {item.total_steps} шагов{item.stopped_at_step ? ` · остановились на шаге ${item.stopped_at_step.index}` : ''}</div></button>; })}</div></div>;
}
