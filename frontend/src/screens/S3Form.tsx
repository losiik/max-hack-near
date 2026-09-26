import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Flex, Typography } from '@maxhub/max-ui';
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
import { AppDialog, ConfirmDialog } from '../components/AppDialog';
import { InlineAction } from '../components/InlineAction';
import { AppIcon, PersonRow } from '../components/UiPrimitives';

type SaveState = 'saved' | 'saving' | 'error';

interface S3FormProps {
  definition: ServiceDefinition;
  initialSession: ServiceSession;
  onRegisterBack?: (handler: (() => void) | null) => void;
  onSessionChange: (session: ServiceSession) => void;
  onConfirmation: (session: ServiceSession) => void;
  assist?: { id: string; status: string; helpers: number; connection: string; recording: boolean; digitalEmployee: boolean } | null;
  onNeedHelp: () => void;
  onOpenWaiting: () => void;
  onEndAssist?: () => void;
  onReleaseDigitalEmployee?: () => void;
}

export function S3Form({ definition, initialSession, onRegisterBack, onSessionChange, onConfirmation, assist, onNeedHelp, onOpenWaiting, onEndAssist, onReleaseDigitalEmployee }: S3FormProps) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState(initialSession);
  const [values, setValues] = useState(initialSession.values);
  const [saveState, setSaveState] = useState<SaveState>('saved');
  const [actionError, setActionError] = useState('');
  const [showConfusionOptions, setShowConfusionOptions] = useState(false);
  const [confirmReleaseAgent, setConfirmReleaseAgent] = useState(false);
  const [confirmEndAssist, setConfirmEndAssist] = useState(false);
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
  const activeHelper = snapshot?.session.participants.find((participant) => participant.role !== 'owner' && participant.status === 'active');
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

  useEffect(() => {
    onRegisterBack?.(session.current_step.index > 1 ? () => { void navigate('back'); } : null);
    return () => onRegisterBack?.(null);
  }, [onRegisterBack, session.current_step.index]);

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
            {assist.status === 'waiting' ? <div className="assist-bar__heading"><StatusMark tone="attention" /><div><strong>Ждём помощника</strong><span>Ссылка отправлена. Можно продолжать оформление.</span></div></div> : activeHelper ? <PersonRow name={activeHelper.display_name} meta={activeHelper.badge?.label ?? 'Помощник рядом'} photoUrl={activeHelper.photo_url} online={activeHelper.online} tone={activeHelper.role === 'ai_agent' ? 'agent' : 'blue'} /> : <div className="assist-bar__heading"><StatusMark tone="attention" /><div><strong>Помощник вышел</strong><span>Сейчас к заявлению никто не подключён.</span></div></div>}
            {assist.status === 'active' && <VoiceControl sessionId={assist.id} role="owner" />}
            {assist.status === 'active' && assist.recording && <div className="recording-state"><span className="recording-dot" />Идёт запись</div>}
            {assist.status === 'active' && assist.digitalEmployee && <><Typography.Text>Цифровой сотрудник рядом — можно задать вопрос голосом.</Typography.Text><InlineAction title="Закончить разговор с агентом" action="Отпустить" variant="destructive" onClick={() => setConfirmReleaseAgent(true)} /></>}
            {assist.connection === 'reconnecting' && <Typography.Text className="assist-bar__state">Восстанавливаем соединение…</Typography.Text>}
            {assist.status === 'waiting' && <InlineAction title="Ожидание помощи" description="Можно управлять приглашением." action="Управлять" variant="secondary" onClick={onOpenWaiting} />}
            {assist.status === 'active' && assist.helpers === 0 && <InlineAction title="Позвать другого" description="Подключите близкого, чтобы продолжить вместе." action="Позвать" variant="secondary" onClick={onNeedHelp} />}
            {assist.status === 'active' && <InlineAction title="Завершить помощь" description="Помощники отключатся от заявления и разговора." action="Завершить" variant="destructive" onClick={() => setConfirmEndAssist(true)} />}
            {assist.status === 'active' && Boolean(sendCommand) && confusionTargets.length > 0 && <>
              <Button size="small" variant="ghost" onClick={() => setShowConfusionOptions((open) => !open)}>Мне здесь непонятно</Button>
              {showConfusionOptions && <AppDialog title="Что стало непонятно?" onClose={() => setShowConfusionOptions(false)}>
                <Typography.Text>Выберите поле — помощник увидит вашу просьбу подсказать.</Typography.Text>
                <Flex direction="column" gap={8}>{confusionTargets.map((element) => <Button key={element.id} size="small" stretched variant="secondary" onClick={() => { sendCommand?.('owner.flag_confusion', { element_id: element.id }); setShowConfusionOptions(false); }}>{element.label}</Button>)}</Flex>
              </AppDialog>}
            </>}
          </Flex>
        ) : (
          <div className="assist-bar__quick-help">
            <div><strong>Не получается?</strong><span>Близкий или специалист подскажут голосом</span></div>
            <Button size="small" stretched variant="secondary" onClick={onNeedHelp}><AppIcon name="people" />Позвать помощь</Button>
          </div>
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

      <Flex gap={8} className="form-actions form-actions--single">
        <Button size="small" stretched onClick={() => void navigate('next')}>Далее</Button>
      </Flex>
      {confirmReleaseAgent && <ConfirmDialog title="Отпустить цифрового сотрудника?" description="Он выйдет из встречи и перестанет слушать вопрос. Позвать снова можно позже." confirmLabel="Отпустить" destructive onCancel={() => setConfirmReleaseAgent(false)} onConfirm={() => { setConfirmReleaseAgent(false); onReleaseDigitalEmployee?.(); }} />}
      {confirmEndAssist && <ConfirmDialog title="Завершить помощь?" description="Помощники отключатся от заявления и разговора." confirmLabel="Завершить" destructive onCancel={() => setConfirmEndAssist(false)} onConfirm={() => { setConfirmEndAssist(false); onEndAssist?.(); }} />}
      {assist?.status === 'active' && snapshot && <AnnotationLayer annotations={snapshot.annotations} pointer={pointer} autoScroll />}
    </Flex>
  );
}
