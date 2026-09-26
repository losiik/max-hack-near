import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteConsultationRecording } from '../api/client';
import { consultationQuery, queryKeys } from '../api/queries';
import { ConfirmDialog } from '../components/AppDialog';
import { useState } from 'react';
import { ScreenIntro } from '../components/ScreenIntro';
import { AppIcon, formatDuration, PersonRow, Surface } from '../components/UiPrimitives';

export function R2Consultation({ id, onReplay }: { id: string; onReplay: () => void }) {
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const detail = useQuery({
    queryKey: queryKeys.consultation(id),
    queryFn: consultationQuery,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => query.state.data?.recording?.status === 'recording' ? 3000 : false,
  });
  const removeRecording = useMutation({ mutationFn: deleteConsultationRecording, onSuccess: () => { setConfirmDelete(false); void queryClient.invalidateQueries({ queryKey: queryKeys.consultation(id) }); void queryClient.invalidateQueries({ queryKey: queryKeys.replay(id) }); } });
  if (detail.isLoading) return <Typography.Text>Загружаем консультацию…</Typography.Text>;
  if (detail.error || !detail.data) return <div className="notice notice--error"><Flex direction="column" gap={8}><Typography.Text>{detail.error instanceof Error ? detail.error.message : 'Не удалось открыть консультацию'}</Typography.Text><Button size="small" onClick={() => void detail.refetch()}>Повторить</Button></Flex></div>;
  const data = detail.data;
  const helpers = data.helpers.map((item) => item.display_name).join(', ') || 'Помощник';
  return <div className="ui-page consultation-detail-screen"><ScreenIntro title={data.service.title} description={`${formatDuration(data.duration_sec)} · пройдено ${data.steps_completed ?? 0} из ${data.total_steps} шагов`} /><Surface><PersonRow name={`Помогал: ${helpers}`} meta={data.recording?.status === 'ready' ? 'Запись встречи сохранена' : 'Запись недоступна'} tone="blue" /><ul className="chapter-list">{data.chapters.map((chapter, index) => <li key={chapter.step_id}><span>{index + 1}</span><div><strong>{chapter.title}</strong><small>{formatDuration(chapter.duration_ms / 1000)} · {chapter.highlights} подсказок{chapter.had_errors ? ' · были ошибки' : ''}</small></div></li>)}</ul></Surface><Surface tone="blue" className="with-icon"><AppIcon name="history" /><p>В истории личные данные не сохраняются — видно только, какие поля были заполнены.</p></Surface><div className="screen-actions"><Button size="small" stretched onClick={onReplay}><AppIcon name="play" />Прослушать встречу</Button>{data.recording?.status === 'ready' && <Button size="small" stretched variant="destructive" onClick={() => setConfirmDelete(true)}>Удалить запись</Button>}</div>{removeRecording.error && <div className="notice notice--error">{removeRecording.error instanceof Error ? removeRecording.error.message : 'Не удалось удалить запись'}</div>}{confirmDelete && <ConfirmDialog title="Удалить запись?" description="Аудиозапись будет удалена без возможности восстановления. История действий останется." confirmLabel="Удалить запись" destructive pending={removeRecording.isPending} onCancel={() => setConfirmDelete(false)} onConfirm={() => removeRecording.mutate(id)} />}</div>;
}
