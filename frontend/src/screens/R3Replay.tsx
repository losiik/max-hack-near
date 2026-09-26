import { Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ConsultationReplay } from '../api/client';
import { queryKeys, recordingQuery, replayQuery } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { AppIcon, Surface } from '../components/UiPrimitives';

type ReplayStep = ConsultationReplay['steps'][number];

interface ReplayChapter extends ReplayStep { offset: number; endOffset: number }
interface ReplayAction {
  key: string;
  offset: number;
  title: string;
  detail?: string;
  count: number;
  groupKey?: string;
}

function seconds(offset: number): string {
  return `${Math.floor(offset / 60_000)}:${String(Math.floor(offset / 1_000) % 60).padStart(2, '0')}`;
}

function fieldLabel(steps: ReplayStep[], elementId: unknown): string {
  const id = String(elementId ?? '');
  const element = steps.flatMap((step) => step.elements).find((item) => item.id === id);
  return element?.label || id.replaceAll('_', ' ') || 'поле';
}

function eventActions(data: ConsultationReplay, chapter: ReplayChapter): ReplayAction[] {
  const participants = new Map(data.participants.map((participant) => [participant.id, participant.display_name]));
  const elements = new Map(data.steps.flatMap((step) => step.elements.map((element) => [element.id, element] as const)));
  const annotationFields = new Map<string, string>();
  const end = chapter.endOffset;
  const actions: ReplayAction[] = [];

  const add = (action: ReplayAction) => {
    const previous = actions.at(-1);
    if (action.groupKey && previous?.groupKey === action.groupKey && action.offset - previous.offset <= 2_000) {
      previous.count += 1;
      return;
    }
    actions.push(action);
  };

  data.events.forEach((event, index) => {
    if (event.type === 'annotation.created') {
      annotationFields.set(String(event.payload.annotation_id ?? ''), String(event.payload.element_id ?? ''));
    }
    if (event.offset_ms < chapter.offset || event.offset_ms >= end) {
      if (event.type === 'annotation.cleared') {
        for (const annotationId of (event.payload.annotation_ids as string[] | undefined) ?? []) annotationFields.delete(annotationId);
      }
      return;
    }
    const actor = event.actor_participant_id ? participants.get(event.actor_participant_id) : null;
    const who = actor || 'Помощник';
    const key = `${event.type}:${event.offset_ms}:${index}`;

    if (event.type === 'annotation.created') {
      const elementId = String(event.payload.element_id ?? '');
      const element = elements.get(elementId);
      const label = fieldLabel(data.steps, elementId);
      const note = typeof event.payload.label === 'string' ? event.payload.label.trim() : '';
      const option = element?.options?.find((item) => item.label === note || item.value === note);
      const title = option
        ? `${who} указал вариант «${option.label}» в поле «${label}»`
        : `${who} указал на поле «${label}»`;
      const availableOptions = element?.options?.map((item) => item.label) ?? [];
      const visibleOptions = availableOptions.slice(0, 5);
      const optionsDetail = availableOptions.length > 5
        ? `Варианты: ${visibleOptions.join(' · ')} · ещё ${availableOptions.length - visibleOptions.length}`
        : `Варианты: ${visibleOptions.join(' · ')}`;
      const detail = option
        ? undefined
        : note
          ? `Пометка помощника: ${note}`
          : availableOptions.length
            ? optionsDetail
            : undefined;
      add({ key, offset: event.offset_ms, title, detail, count: 1, groupKey: `annotation:${actor ?? ''}:${elementId}:${note}` });
      return;
    }

    if (event.type === 'owner.confusion_flagged') {
      const elementId = String(event.payload.element_id ?? '');
      add({
        key,
        offset: event.offset_ms,
        title: `Владелец попросил подсказать по полю «${fieldLabel(data.steps, elementId)}»`,
        count: 1,
        groupKey: `confusion:${elementId}`,
      });
      return;
    }

    if (event.type === 'annotation.cleared') {
      const annotationIds = (event.payload.annotation_ids as string[] | undefined) ?? [];
      const labels = [...new Set(annotationIds.map((annotationId) => annotationFields.get(annotationId)).filter((elementId): elementId is string => Boolean(elementId)))];
      annotationIds.forEach((annotationId) => annotationFields.delete(annotationId));
      const subject = labels.length ? `: ${labels.map((elementId) => `«${fieldLabel(data.steps, elementId)}»`).join(', ')}` : '';
      add({ key, offset: event.offset_ms, title: `${who} убрал указку${subject}`, count: 1 });
      return;
    }

    if (event.type === 'form.field_updated') {
      const ids = (event.payload.element_ids as string[] | undefined) ?? [];
      const states = event.payload.states as Record<string, string> | undefined;
      ids.forEach((elementId) => {
        const state = states?.[elementId];
        const action = state === 'filled' ? 'заполнено' : state === 'empty' ? 'очищено' : 'изменено';
        add({ key: `${key}:${elementId}`, offset: event.offset_ms, title: `Поле «${fieldLabel(data.steps, elementId)}» ${action}`, count: 1 });
      });
      return;
    }

    if (event.type === 'form.validation_failed') {
      const errors = (event.payload.errors as Array<{ element_id: string }> | undefined) ?? [];
      errors.forEach((error) => add({
        key: `${key}:${error.element_id}`,
        offset: event.offset_ms,
        title: `Нужно исправить поле «${fieldLabel(data.steps, error.element_id)}»`,
        count: 1,
      }));
      return;
    }

    if (event.type === 'participant.joined') {
      const participantId = String(event.payload.participant_id ?? '');
      const name = participants.get(participantId) || 'Помощник';
      add({ key, offset: event.offset_ms, title: `${name} подключился к встрече`, count: 1 });
    }
  });

  return actions;
}

export function R3Replay({ id }: { id: string }) {
  const replay = useQuery({
    queryKey: queryKeys.replay(id),
    queryFn: replayQuery,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => query.state.data?.recording?.status === 'recording' ? 3000 : false,
  });
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
  const [expandedChapterId, setExpandedChapterId] = useState<string | null>(null);

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
    const filled = new Set<string>();
    const errors = new Set<string>();
    for (const event of data.events) {
      if (event.offset_ms > position) break;
      if (event.type === 'navigation.step_changed') stepId = String(event.payload.to_step_id);
      if (event.type === 'form.field_updated') {
        const states = event.payload.states as Record<string, string> | undefined;
        for (const field of (event.payload.element_ids as string[] | undefined) ?? []) {
          if (states?.[field] === 'filled') filled.add(field);
          else if (states?.[field] === 'empty') filled.delete(field);
        }
      }
      if (event.type === 'form.validation_failed') {
        for (const error of (event.payload.errors as Array<{ element_id: string }> | undefined) ?? []) errors.add(error.element_id);
      }
    }
    return { step: data.steps.find((item) => item.id === stepId) ?? data.steps[0], filled, errors };
  }, [data, position]);

  const chapters = useMemo<ReplayChapter[]>(() => {
    if (!data) return [];
    const starts = data.steps.map((step, index) => {
      if (index === 0) return { ...step, offset: 0 };
      const event = data.events.find((item) => item.type === 'navigation.step_changed' && String(item.payload.to_step_id) === step.id);
      return { ...step, offset: event?.offset_ms ?? 0 };
    });
    return starts.map((chapter, index) => ({
      ...chapter,
      endOffset: starts[index + 1]?.offset ?? data.duration_ms + 1,
    }));
  }, [data]);

  if (replay.isLoading) return <Typography.Text>Готовим replay…</Typography.Text>;
  if (replay.error || !data || !state) {
    return <div className="notice notice--error">{replay.error instanceof Error ? replay.error.message : 'Не удалось загрузить replay'}</div>;
  }

  const loadedData = data;
  function seek(next: number) {
    setPosition(next);
    if (audio.current && loadedData.recording?.offset_ms !== null && loadedData.recording?.offset_ms !== undefined) {
      audio.current.currentTime = Math.max(0, (next - loadedData.recording.offset_ms) / 1000);
    }
  }
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
  function cycleSpeed() {
    const next = speed === 1 ? 1.5 : speed === 1.5 ? 2 : 1;
    setSpeed(next);
    if (audio.current) audio.current.playbackRate = next;
  }

  const recordingMessage = recording.isLoading
    ? 'Загружаем аудиозапись…'
    : recording.error
      ? 'Не удалось получить аудиозапись. Повторите попытку позже.'
      : loadedData.recording?.status === 'recording'
        ? 'Аудиозапись ещё обрабатывается.'
        : 'Аудиозапись недоступна. Можно посмотреть сохранённые действия.';

  return (
    <div className="ui-page replay-screen">
      <ScreenIntro title="Прослушать встречу" description={`${loadedData.service.title} · личные данные в истории не сохраняются`} />
      {recordingUrl ? (
        <Surface className="replay-player">
          <audio
            ref={audio}
            preload="metadata"
            src={recordingUrl}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onTimeUpdate={(event) => setPosition((loadedData.recording?.offset_ms ?? 0) + event.currentTarget.currentTime * 1000)}
          />
          <input className="replay-range" aria-label="Позиция записи" type="range" min="0" max={loadedData.duration_ms} value={position} onChange={(event) => seek(Number(event.target.value))} />
          <div className="replay-time"><span>{seconds(position)}</span><span>{seconds(loadedData.duration_ms)}</span></div>
          <div className="replay-controls">
            <button type="button" aria-label="Назад на 15 секунд" onClick={() => skip(-15_000)}><AppIcon name="rewind" /></button>
            <button type="button" className="replay-controls__main" aria-label={playing ? 'Пауза' : 'Воспроизвести'} onClick={() => void togglePlayback()}><AppIcon name={playing ? 'pause' : 'play'} /></button>
            <button type="button" aria-label="Вперёд на 15 секунд" onClick={() => skip(15_000)}><AppIcon name="forward" /></button>
            <button type="button" className="replay-speed" onClick={cycleSpeed}>{speed}×</button>
          </div>
        </Surface>
      ) : <Surface tone="warning"><Typography.Text>{recordingMessage}</Typography.Text></Surface>}

      {state.step && <>
        <div className="projection-caption">Что было на экране в {seconds(position)}</div>
        <Surface className="replay-form">
          <div className="replay-step">Шаг {state.step.index} · {state.step.title}</div>
          <Flex direction="column" gap={8}>
            {state.step.elements.map((element) => <div className="projected-field" key={element.id}>
              <Typography.Text>{element.label || 'Поле'}</Typography.Text>
              <Typography.Text className={state.filled.has(element.id) ? 'field-state is-filled' : 'field-state'}>
                {state.errors.has(element.id) ? 'Требует исправления' : state.filled.has(element.id) ? 'Заполнено' : 'Не заполнено'}
              </Typography.Text>
            </div>)}
          </Flex>
        </Surface>
      </>}

      <section className="replay-chapters">
        <h2>Главы</h2>
        <ul className="chapter-list ui-surface">
          {chapters.map((chapter) => {
            const expanded = expandedChapterId === chapter.id;
            const actions = expanded ? eventActions(loadedData, chapter) : [];
            return <li key={chapter.id} className={`${state.step?.id === chapter.id ? 'is-active' : ''}${expanded ? ' is-expanded' : ''}`}>
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => {
                  setExpandedChapterId(expanded ? null : chapter.id);
                  seek(chapter.offset);
                }}
              >
                <span>{chapter.index}</span>
                <span><strong>{chapter.title}</strong><small>{seconds(chapter.offset)} · {seconds(Math.max(0, chapter.endOffset - chapter.offset))}</small></span>
                <AppIcon name="chevron" className="chapter-list__chevron" />
              </button>
              {expanded && <div className="chapter-actions">
                {actions.length ? <ol>
                  {actions.map((action) => <li key={action.key}>
                    <button type="button" className="chapter-action" onClick={() => seek(action.offset)}>
                      <time>{seconds(action.offset)}</time>
                      <span className="chapter-action__copy">
                        <strong>{action.title}{action.count > 1 ? ` ×${action.count}` : ''}</strong>
                        {action.detail && <small>{action.detail}</small>}
                      </span>
                    </button>
                  </li>)}
                </ol> : <Typography.Text className="muted-text">В этой главе нет записанных действий.</Typography.Text>}
              </div>}
            </li>;
          })}
        </ul>
      </section>
    </div>
  );
}
