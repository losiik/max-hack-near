import { Button, CellList, CellSimple, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteConsultationRecording } from '../api/client';
import { consultationQuery, queryKeys } from '../api/queries';
import { ConfirmDialog } from '../components/AppDialog';
import { useState } from 'react';
import { ScreenIntro } from '../components/ScreenIntro';

export function R2Consultation({ id, onReplay }: { id: string; onReplay: () => void }) {
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const detail = useQuery({ queryKey: queryKeys.consultation(id), queryFn: consultationQuery });
  const removeRecording = useMutation({ mutationFn: deleteConsultationRecording, onSuccess: () => { setConfirmDelete(false); void queryClient.invalidateQueries({ queryKey: queryKeys.consultation(id) }); void queryClient.invalidateQueries({ queryKey: queryKeys.replay(id) }); } });
  if (detail.isLoading) return <Typography.Text>Загружаем консультацию…</Typography.Text>;
  if (detail.error || !detail.data) return <div className="notice notice--error"><Flex direction="column" gap={8}><Typography.Text>{detail.error instanceof Error ? detail.error.message : 'Не удалось открыть консультацию'}</Typography.Text><Button size="small" onClick={() => void detail.refetch()}>Повторить</Button></Flex></div>;
  const data = detail.data;
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="История помощи" title={data.service.title} description={`Помогал: ${data.helpers.map((item) => item.display_name).join(', ') || 'помощник'}`} meta={`Пройдено ${data.steps_completed ?? 0} из ${data.total_steps} шагов`} /><CellList mode="island" filled>{data.chapters.map((chapter) => <CellSimple key={chapter.step_id} surface="island" title={chapter.title} subtitle={`Подсветок: ${chapter.highlights} · вопросов: ${chapter.confusions}${chapter.had_errors ? ' · были ошибки' : ''}`} />)}</CellList><Button size="small" stretched onClick={onReplay}>Пересмотреть консультацию</Button>{data.recording?.status === 'ready' && <Button size="small" stretched variant="destructive" onClick={() => setConfirmDelete(true)}>Удалить запись</Button>}{removeRecording.error && <div className="notice notice--error">{removeRecording.error instanceof Error ? removeRecording.error.message : 'Не удалось удалить запись'}</div>}{confirmDelete && <ConfirmDialog title="Удалить запись?" description="Аудиозапись будет удалена без возможности восстановления. История действий останется." confirmLabel="Удалить запись" destructive pending={removeRecording.isPending} onCancel={() => setConfirmDelete(false)} onConfirm={() => removeRecording.mutate(id)} />}</Flex>;
}
