import { Button, Flex, Typography } from '@maxhub/max-ui';
import { Fragment, useEffect, useRef, useState, type PointerEvent } from 'react';
import type { ProjectedState } from '../api/client';
import { AnnotationToolbar, type AnnotationKind } from '../components/AnnotationToolbar';
import { ProjectedField } from '../components/ProjectedField';
import { useAssistStore } from '../realtime/assistStore';
import { VoiceControl } from '../components/VoiceControl';
import { ConfirmDialog } from '../components/AppDialog';
import { useToast } from '../components/ToastProvider';
import { PersonRow } from '../components/UiPrimitives';

export function H3Helper({ snapshot, connection, onLeave }: { snapshot: ProjectedState; connection: string; onLeave: () => void }) {
  const owner = snapshot.session.owner;
  const sendCommand = useAssistStore((state) => state.sendCommand);
  const confusionElementId = useAssistStore((state) => state.confusionElementId);
  const selectView = useAssistStore((state) => state.selectView);
  const annotationFeedback = useAssistStore((state) => state.annotationFeedback);
  const [kind, setKind] = useState<AnnotationKind>('highlight');
  const [label, setLabel] = useState('');
  const [confirmLeave, setConfirmLeave] = useState(false);
  const lastPointerAt = useRef(0);
  const lastFeedback = useRef('');
  const toast = useToast();
  const canAnnotate = Boolean(sendCommand && snapshot.session.me.capabilities.includes('annotate'));
  const ownerParticipant = snapshot.session.participants.find((participant) => participant.role === 'owner');
  const canSeeHints = snapshot.session.me.capabilities.includes('view_operator_hints');

  useEffect(() => {
    if (!annotationFeedback || annotationFeedback.state === 'sending') return;
    const key = `${annotationFeedback.requestId}:${annotationFeedback.state}`;
    if (key === lastFeedback.current) return;
    lastFeedback.current = key;
    toast(annotationFeedback.message, annotationFeedback.state === 'error' ? 'error' : 'default');
  }, [annotationFeedback, toast]);

  function point(elementId: string, event: PointerEvent<HTMLElement>) {
    if (kind !== 'pointer' || !sendCommand || Date.now() - lastPointerAt.current < 100) return;
    const rect = event.currentTarget.getBoundingClientRect();
    lastPointerAt.current = Date.now();
    sendCommand('annotation.pointer', {
      element_id: elementId,
      rel_x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
      rel_y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
    });
  }

  function showAnnotation(elementId: string) {
    if (!sendCommand || kind === 'pointer') return;
    const trimmed = label.trim();
    sendCommand(`annotation.${kind}`, trimmed ? { element_id: elementId, label: trimmed } : { element_id: elementId });
  }

  const ownerOnline = ownerParticipant?.online === true;
  return (
    <div className="helper-screen">
      <header className="helper-head">
        <PersonRow name={`Вы помогаете ${owner.display_name}`} meta={<><span className={connection === 'connected' && ownerOnline ? 'text-positive' : 'text-attention'}>{connection === 'reconnecting' ? 'восстанавливаем соединение' : connection === 'connected' && ownerOnline ? 'в сети' : 'нет соединения'}</span> · шаг {snapshot.current_step.index} из {snapshot.service.total_steps} · {snapshot.current_step.title}</>} photoUrl={owner.photo_url} tone="green" online={connection === 'connected' && ownerOnline} />
        <VoiceControl sessionId={snapshot.session.id} role="helper" autoConnect={false} />
        {snapshot.session.recording?.status === 'recording' && <div className="recording-state"><span className="recording-dot" />Идёт запись</div>}
        <Button size="small" stretched variant="destructive" onClick={() => setConfirmLeave(true)}>Выйти из помощи</Button>
      </header>
      <main className="helper-content">
      {canSeeHints && snapshot.current_step.operator_hint && <div className="notice notice--subtle"><Typography.Label>Подсказка специалисту</Typography.Label><Typography.Text>{snapshot.current_step.operator_hint}</Typography.Text></div>}
      {confusionElementId && <div className="notice notice--subtle">{owner.display_name} просит подсказать по полю «{snapshot.current_step.elements.find((element) => element.id === confusionElementId)?.label ?? 'этому полю'}».</div>}
      {annotationFeedback?.state === 'sending' && <Typography.Text className="muted-text">{annotationFeedback.message}</Typography.Text>}
      {annotationFeedback?.state === 'error' && <div className="notice notice--error"><Typography.Text>{annotationFeedback.message}</Typography.Text></div>}
      {kind === 'pointer' && canAnnotate && <div className="notice notice--subtle">Ведите пальцем по нужному полю — владелец увидит указку.</div>}
      <div className="helper-projection-heading"><Typography.Label>{owner.display_name} сейчас видит этот шаг</Typography.Label></div>
      <Flex direction="column" gap={12} className="helper-projection">
        {snapshot.current_step.elements.map((element) => <Fragment key={element.id}>
          <ProjectedField
            element={element}
            error={snapshot.errors.find((error) => error.element_id === element.id)}
            confusion={confusionElementId === element.id}
            selectView={selectView}
            interactive={canAnnotate && !['info', 'summary', 'action'].includes(element.type)}
            onShow={showAnnotation}
            onPointer={kind === 'pointer' ? point : undefined}
            onPointerEnd={kind === 'pointer' ? () => sendCommand?.('annotation.pointer', { visible: false }) : undefined}
          />
          {canSeeHints && element.operator_hint && <Typography.Text className="operator-hint">Подсказка: {element.operator_hint}</Typography.Text>}
        </Fragment>)}
      </Flex>
      {canAnnotate && <AnnotationToolbar kind={kind} label={label} onKindChange={setKind} onLabelChange={setLabel} onClear={() => sendCommand?.('annotation.clear', {})} />}
      </main>
      {confirmLeave && <ConfirmDialog title="Выйти из помощи?" description="Вы перестанете видеть заявление и участвовать в разговоре." confirmLabel="Выйти" destructive onCancel={() => setConfirmLeave(false)} onConfirm={onLeave} />}
    </div>
  );
}
