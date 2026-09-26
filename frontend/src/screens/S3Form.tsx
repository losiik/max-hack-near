import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Flex, IconButton, Typography } from '@maxhub/max-ui';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FormRenderer } from '../components/FormRenderer';
import { AnnotationLayer } from '../components/AnnotationLayer';
import {
  ApiError,
  navigateService,
  updateServiceFields,
  type ServiceDefinition,
  type ServiceSession,
} from '../api/client';
import { cacheSession } from '../api/queries';
import { setClosingConfirmation, setScreenCaptureProtection } from '../platform/maxBridge';
import { ScreenIntro, StatusMark } from '../components/ScreenIntro';
import { useAssistStore } from '../realtime/assistStore';
import { VoiceControl } from '../components/VoiceControl';
import { PastHelpBanner } from '../components/PastHelpBanner';

type SaveState = 'saved' | 'saving' | 'error';

function ArrowLeftIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m14.5 5-7 7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface S3FormProps {
  definition: ServiceDefinition;
  initialSession: ServiceSession;
  onSessionChange: (session: ServiceSession) => void;
  onConfirmation: (session: ServiceSession) => void;
  assist?: { id: string; status: string; helpers: number; connection: string; recording: boolean } | null;
  onNeedHelp: () => void;
  onOpenWaiting: () => void;
}

export function S3Form({ definition, initialSession, onSessionChange, onConfirmation, assist, onNeedHelp, onOpenWaiting }: S3FormProps) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState(initialSession);
  const [values, setValues] = useState(initialSession.values);
  const [saveState, setSaveState] = useState<SaveState>('saved');
  const [actionError, setActionError] = useState('');
  const [showConfusionOptions, setShowConfusionOptions] = useState(false);
  const pendingValues = useRef<Record<string, unknown>>({});
  const timer = useRef<number | undefined>(undefined);
  const sessionRef = useRef(initialSession);
  const snapshot = useAssistStore((state) => state.snapshot);
  const pointer = useAssistStore((state) => state.pointer);
  const sendCommand = useAssistStore((state) => state.sendCommand);
  const { mutateAsync: saveFields } = useMutation({
    mutationFn: ({ values, version }: { values: Record<string, unknown>; version: number }) =>
      updateServiceFields(sessionRef.current.id, values, version),
    onSuccess: (next) => cacheSession(queryClient, next),
  });
  const { mutateAsync: navigateFields } = useMutation({
    mutationFn: ({ action }: { action: 'next' | 'back' }) => navigateService(sessionRef.current.id, action),
    onSuccess: (next) => cacheSession(queryClient, next),
  });

  const applySession = useCallback(
    (next: ServiceSession) => {
      sessionRef.current = next;
      setSession(next);
      setValues(next.values);
      onSessionChange(next);
    },
    [onSessionChange],
  );

  const flush = useCallback(async (): Promise<boolean> => {
    const patch = pendingValues.current;
    if (!Object.keys(patch).length) return true;
    pendingValues.current = {};
    setSaveState('saving');
    try {
      const next = await saveFields({ values: patch, version: sessionRef.current.version });
      applySession(next);
      setSaveState('saved');
      return true;
    } catch (reason) {
      const current = reason instanceof ApiError ? (reason.details?.current as ServiceSession | undefined) : undefined;
      if (current?.id === sessionRef.current.id) {
        applySession(current);
        setActionError('Черновик изменился в другой вкладке. Показаны актуальные данные.');
      } else {
        pendingValues.current = { ...patch, ...pendingValues.current };
        setActionError(reason instanceof Error ? reason.message : 'Не удалось сохранить изменения');
      }
      setSaveState('error');
      return false;
    }
  }, [applySession, saveFields]);

  useEffect(() => {
    setClosingConfirmation(true);
    return () => {
      window.clearTimeout(timer.current);
      void flush();
      setClosingConfirmation(false);
    };
  }, [flush]);

  useEffect(() => {
    if (!assist || assist.status !== 'active') return;
    setScreenCaptureProtection(true);
    return () => setScreenCaptureProtection(false);
  }, [assist?.status]);

  const updateValue = (elementId: string, value: string | number | boolean | null) => {
    setValues((current) => ({ ...current, [elementId]: value }));
    pendingValues.current = { ...pendingValues.current, [elementId]: value };
    setSaveState('saving');
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), 500);
  };

  const currentStep = definition.steps.find((step) => step.id === session.current_step.id);
  const confusionTargets = currentStep?.elements.filter((element) => {
    if (!element.label || ['info', 'summary', 'action'].includes(element.type)) return false;
    const condition = element.visible_if;
    if (!condition) return true;
    const value = values[condition.element];
    return condition.in ? condition.in.includes(value) : value === condition.equals;
  }) ?? [];

  async function navigate(action: 'next' | 'back') {
    setActionError('');
    if (!(await flush())) return;
    try {
      const next = await navigateFields({ action });
      applySession(next);
      if (next.current_step.id === 'confirmation') onConfirmation(next);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : 'Не удалось перейти к следующему шагу');
    }
  }

  if (!currentStep) return null;

  return (
    <Flex direction="column" gap={12} className="service-form">
      <ScreenIntro
        eyebrow={`Шаг ${session.current_step.index} из ${session.total_steps}`}
        title={currentStep.title}
        description={currentStep.description}
      />
      <div className="progress-track" aria-label={`Шаг ${session.current_step.index} из ${session.total_steps}`}>
        <span style={{ width: `${(session.current_step.index / session.total_steps) * 100}%` }} />
      </div>

      {(!assist || assist.status !== 'active') && <PastHelpBanner serviceSessionId={session.id} stepId={session.current_step.id} />}

      <section className={`assist-bar assist-bar--${assist ? assist.status : 'idle'}`}>
        {assist ? (
          <Flex direction="column" gap={8}>
            <Flex align="center" gap={8}><StatusMark tone={assist.status === 'active' ? 'positive' : 'attention'} /><Typography.Label>{assist.status === 'waiting' ? 'Помощь ожидает подключения' : 'Помощник рядом'}</Typography.Label></Flex>
            <Typography.Text>{assist.status === 'waiting' ? 'Ссылка отправлена. Можно продолжать оформление.' : `${assist.helpers || 1} участник рядом с вами`}</Typography.Text>
            {assist.status === 'active' && <VoiceControl sessionId={assist.id} />}
            {assist.status === 'active' && assist.recording && <Typography.Text className="recording-state">● Идёт запись</Typography.Text>}
            {assist.connection === 'reconnecting' && <Typography.Text className="assist-bar__state">Восстанавливаем соединение…</Typography.Text>}
            <Button size="small" variant="secondary" onClick={onOpenWaiting}>{assist.status === 'waiting' ? 'Открыть ожидание' : 'Открыть помощь'}</Button>
            {assist.status === 'active' && Boolean(sendCommand) && confusionTargets.length > 0 && <>
              <Button size="small" variant="ghost" onClick={() => setShowConfusionOptions((open) => !open)}>Мне здесь непонятно</Button>
              {showConfusionOptions && <div className="confusion-options">
                <Typography.Text>Выберите поле — помощник увидит сигнал.</Typography.Text>
                <Flex direction="column" gap={8}>{confusionTargets.map((element) => <Button key={element.id} size="small" variant="secondary" onClick={() => { sendCommand?.('owner.flag_confusion', { element_id: element.id }); setShowConfusionOptions(false); }}>{element.label}</Button>)}</Flex>
              </div>}
            </>}
          </Flex>
        ) : (
          <Flex direction="column" gap={12} className="assist-bar__idle-content">
            <Flex direction="column" gap={4} className="assist-bar__copy">
              <Typography.Label>Если станет непонятно</Typography.Label>
              <Typography.Text>Позовите близкого — он подскажет голосом.</Typography.Text>
            </Flex>
            <Button size="small" stretched onClick={onNeedHelp}>Нужна помощь</Button>
          </Flex>
        )}
      </section>

      {actionError && <div className="notice notice--error">{actionError}</div>}
      <FormRenderer
        definition={definition}
        step={currentStep}
        values={values}
        errors={session.errors}
        onChange={updateValue}
        onBlur={() => void flush()}
        showPrivacyHints={assist?.status === 'active'}
      />

      <Typography.Text className="save-state">
        {saveState === 'saving' ? 'Сохраняем…' : saveState === 'error' ? 'Изменения не сохранены' : 'Сохранено'}
      </Typography.Text>

      <Flex gap={12} className="form-actions">
        <IconButton
          size="small"
          variant="secondary"
          aria-label="Назад"
          title="Назад"
          disabled={session.current_step.index === 1}
          onClick={() => void navigate('back')}
        >
          <ArrowLeftIcon />
        </IconButton>
        <Button size="small" stretched onClick={() => void navigate('next')}>Далее</Button>
      </Flex>
      {assist?.status === 'active' && snapshot && <AnnotationLayer annotations={snapshot.annotations} pointer={pointer} autoScroll />}
    </Flex>
  );
}
