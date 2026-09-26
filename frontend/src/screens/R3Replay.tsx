import { Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { queryKeys, recordingQuery, replayQuery } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { AppIcon, Surface } from '../components/UiPrimitives';

function seconds(offset: number): string { return `${Math.floor(offset / 60_000)}:${String(Math.floor(offset / 1_000) % 60).padStart(2, '0')}`; }

export function R3Replay({ id }: { id: string }) {
  const replay = useQuery({ queryKey: queryKeys.replay(id), queryFn: replayQuery });
  const recording = useQuery({
    queryKey: queryKeys.recording(id),
    queryFn: recordingQuery,
    enabled: replay.data?.recording?.status === 'ready' && Boolean(replay.data.recording.url),
    retry: false,
  });
  const audio = useRef<HTMLAudioElement>(null);
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!recording.data) {
      setRecordingUrl(null);
      return;
    }
    const url = URL.createObjectURL(recording.data);
    setRecordingUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [recording.data]);
  const data = replay.data;
  const state = useMemo(() => {
    if (!data) return null;
    let stepId = data.steps[0]?.id;
    const filled = new Set<string>(); const errors = new Set<string>(); const annotations = new Map<string, { kind: string; label: string | null }>();
    for (const event of data.events) {
      if (event.offset_ms > position) break;
      if (event.type === 'navigation.step_changed') stepId = String(event.payload.to_step_id);
      if (event.type === 'form.field_updated') for (const field of (event.payload.element_ids as string[] ?? [])) { if ((event.payload.states as Record<string, string> | undefined)?.[field] === 'filled') filled.add(field); }
      if (event.type === 'form.validation_failed') for (const error of (event.payload.errors as Array<{ element_id: string }> ?? [])) errors.add(error.element_id);
      if (event.type === 'annotation.created') annotations.set(String(event.payload.annotation_id), { kind: String(event.payload.kind), label: event.payload.label as string | null });
      if (event.type === 'annotation.cleared') for (const annotationId of (event.payload.annotation_ids as string[] ?? [])) annotations.delete(annotationId);
    }
    return { step: data.steps.find((item) => item.id === stepId) ?? data.steps[0], filled, errors, annotations: [...annotations.values()] };
  }, [data, position]);
  const chapters = useMemo(() => {
    if (!data) return [];
    return data.steps.map((step, index) => {
      if (index === 0) return { ...step, offset: 0 };
      const event = data.events.find((item) => item.type === 'navigation.step_changed' && String(item.payload.to_step_id) === step.id);
      return { ...step, offset: event?.offset_ms ?? 0 };
    });
  }, [data]);
  if (replay.isLoading) return <Typography.Text>Готовим replay…</Typography.Text>;
  if (replay.error || !data || !state) return <div className="notice notice--error">{replay.error instanceof Error ? replay.error.message : 'Не удалось загрузить replay'}</div>;
  const loadedData = data;
  function seek(next: number) { setPosition(next); if (audio.current && loadedData.recording?.offset_ms !== null && loadedData.recording?.offset_ms !== undefined) audio.current.currentTime = Math.max(0, (next - loadedData.recording.offset_ms) / 1000); }
  async function togglePlayback() {
    if (!audio.current) return;
    if (!audio.current.paused) {
      audio.current.pause();
      return;
    }
    try {
      await audio.current.play();
    } catch {
      setPlaying(false);
    }
  }
  function skip(delta: number) { seek(Math.min(loadedData.duration_ms, Math.max(0, position + delta))); }
  function cycleSpeed() { const next = speed === 1 ? 1.5 : speed === 1.5 ? 2 : 1; setSpeed(next); if (audio.current) audio.current.playbackRate = next; }
  const recordingMessage = recording.isLoading ? 'Загружаем аудиозапись…' : recording.error ? 'Не удалось получить аудиозапись. Повторите попытку позже.' : loadedData.recording?.status === 'recording' ? 'Аудиозапись ещё обрабатывается.' : 'Аудиозапись недоступна. Можно посмотреть сохранённые подсказки.';
  return <div className="ui-page replay-screen"><ScreenIntro title="Прослушать встречу" description={`${loadedData.service.title} · личные данные в истории не сохраняются`} />{recordingUrl ? <Surface className="replay-player"><audio ref={audio} preload="metadata" src={recordingUrl} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onTimeUpdate={(event) => setPosition((loadedData.recording?.offset_ms ?? 0) + event.currentTarget.currentTime * 1000)} /><input className="replay-range" aria-label="Позиция записи" type="range" min="0" max={loadedData.duration_ms} value={position} onChange={(event) => seek(Number(event.target.value))} /><div className="replay-time"><span>{seconds(position)}</span><span>{seconds(loadedData.duration_ms)}</span></div><div className="replay-controls"><button type="button" aria-label="Назад на 15 секунд" onClick={() => skip(-15_000)}><AppIcon name="rewind" /></button><button type="button" className="replay-controls__main" aria-label={playing ? 'Пауза' : 'Воспроизвести'} onClick={() => void togglePlayback()}><AppIcon name={playing ? 'pause' : 'play'} /></button><button type="button" aria-label="Вперёд на 15 секунд" onClick={() => skip(15_000)}><AppIcon name="forward" /></button><button type="button" className="replay-speed" onClick={cycleSpeed}>{speed}×</button></div></Surface> : <Surface tone="warning"><Typography.Text>{recordingMessage}</Typography.Text></Surface>}{state.step && <><div className="projection-caption">Что было на экране в {seconds(position)}</div><Surface className="replay-form"><div className="replay-step">Шаг {state.step.index} · {state.step.title}</div><Flex direction="column" gap={8}>{state.step.elements.map((element) => <div className="projected-field" key={element.id}><Typography.Text>{element.label || 'Поле'}</Typography.Text><Typography.Text className={state.filled.has(element.id) ? 'field-state is-filled' : 'field-state'}>{state.errors.has(element.id) ? 'Требует исправления' : state.filled.has(element.id) ? 'Заполнено' : 'Не заполнено'}</Typography.Text></div>)}</Flex>{state.annotations.map((annotation, index) => <div className="annotation-replay" key={index}><AppIcon name="edit" /><span>{annotation.label || 'Помощник показал это поле'}</span></div>)}</Surface></>}<section className="replay-chapters"><h2>Главы</h2><ul className="chapter-list ui-surface">{chapters.map((chapter) => <li key={chapter.id} className={state.step?.id === chapter.id ? 'is-active' : ''}><button type="button" onClick={() => seek(chapter.offset)}><span>{chapter.index}</span><span><strong>{chapter.title}</strong><small>{seconds(chapter.offset)}</small></span></button></li>)}</ul></section></div>;
}
