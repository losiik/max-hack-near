import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useRef, useState } from 'react';
import { queryKeys, replayQuery } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { getAccessToken } from '../api/client';

function seconds(offset: number): string { return `${Math.floor(offset / 60_000)}:${String(Math.floor(offset / 1_000) % 60).padStart(2, '0')}`; }

export function R3Replay({ id }: { id: string }) {
  const replay = useQuery({ queryKey: queryKeys.replay(id), queryFn: replayQuery });
  const audio = useRef<HTMLAudioElement>(null);
  const [position, setPosition] = useState(0);
  if (replay.isLoading) return <Typography.Text>Готовим replay…</Typography.Text>;
  if (replay.error || !replay.data) return <div className="notice notice--error">{replay.error instanceof Error ? replay.error.message : 'Не удалось загрузить replay'}</div>;
  const data = replay.data;
  const state = useMemo(() => {
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
  const recordingUrl = data.recording?.url ? `${data.recording.url}${data.recording.url.includes('?') ? '&' : '?'}token=${encodeURIComponent(getAccessToken())}` : null;
  function seek(next: number) { setPosition(next); if (audio.current && data.recording?.offset_ms !== null && data.recording?.offset_ms !== undefined) audio.current.currentTime = Math.max(0, (next - data.recording.offset_ms) / 1000); }
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="История помощи" title="Пересмотреть консультацию" description="Значения формы скрыты даже для владельца." />{recordingUrl ? <audio ref={audio} controls preload="metadata" src={recordingUrl} onTimeUpdate={(event) => setPosition((data.recording?.offset_ms ?? 0) + event.currentTarget.currentTime * 1000)} /> : <Typography.Text className="muted-text">Аудиозапись недоступна.</Typography.Text>}<label className="replay-timeline"><Typography.Label>{seconds(position)} из {seconds(data.duration_ms)}</Typography.Label><input type="range" min="0" max={data.duration_ms} value={position} onChange={(event) => seek(Number(event.target.value))} /></label>{state.step && <section className="replay-form"><Typography.Label>На экране был шаг {state.step.index} из {data.steps.length}</Typography.Label><Typography.Headline>{state.step.title}</Typography.Headline><Flex direction="column" gap={8}>{state.step.elements.map((element) => <div className="projected-field" key={element.id}><Typography.Text>{element.label || 'Поле'}</Typography.Text><Typography.Text className="muted-text">{state.errors.has(element.id) ? 'Требует исправления' : state.filled.has(element.id) ? '✓ заполнено' : 'Не заполнено'}</Typography.Text></div>)}</Flex>{state.annotations.map((annotation, index) => <div className="notice notice--subtle" key={index}><Typography.Text>{annotation.kind === 'highlight' ? 'Подсветка' : annotation.kind}: {annotation.label || 'без подписи'}</Typography.Text></div>)}</section>}<Flex direction="column" gap={8}>{data.events.map((event, index) => <Button key={`${event.seq ?? 'event'}-${index}`} size="small" stretched variant={event.offset_ms <= position ? 'secondary' : 'ghost'} onClick={() => seek(event.offset_ms)}>{seconds(event.offset_ms)} · {event.type.replaceAll('.', ' · ')}</Button>)}</Flex></Flex>;
}
