import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useRef, useState, type PointerEvent } from 'react';
import type { ProjectedState } from '../api/client';
import { AnnotationToolbar, type AnnotationKind } from '../components/AnnotationToolbar';
import { ProjectedField } from '../components/ProjectedField';
import { ScreenIntro, StatusMark } from '../components/ScreenIntro';
import { useAssistStore } from '../realtime/assistStore';

export function H3Helper({ snapshot, connection, onLeave }: { snapshot: ProjectedState; connection: string; onLeave: () => void }) {
  const owner = snapshot.session.owner;
  const sendCommand = useAssistStore((state) => state.sendCommand);
  const confusionElementId = useAssistStore((state) => state.confusionElementId);
  const [kind, setKind] = useState<AnnotationKind>('highlight');
  const [label, setLabel] = useState('Нажмите сюда');
  const lastPointerAt = useRef(0);
  const canAnnotate = Boolean(sendCommand && snapshot.session.me.capabilities.includes('annotate'));

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

  return (
    <Flex direction="column" gap={12}>
      <ScreenIntro eyebrow={`Вы помогаете ${owner.display_name}`} title={snapshot.current_step.title} meta={`Шаг ${snapshot.current_step.index} из ${snapshot.service.total_steps}`} />
      {connection === 'reconnecting' && <div className="notice notice--subtle">Восстанавливаем соединение…</div>}
      {snapshot.session.recording?.status === 'recording' && <div className="recording-state"><StatusMark tone="attention" /><Typography.Text>Идёт запись</Typography.Text></div>}
      {confusionElementId && <div className="notice notice--subtle">{owner.display_name} просит подсказать по полю «{snapshot.current_step.elements.find((element) => element.id === confusionElementId)?.label ?? 'этому полю'}».</div>}
      {canAnnotate && <AnnotationToolbar kind={kind} label={label} onKindChange={setKind} onLabelChange={setLabel} onClear={() => sendCommand?.('annotation.clear', {})} />}
      <Flex direction="column" gap={12}>
        {snapshot.current_step.elements.map((element) => (
          <ProjectedField
            key={element.id}
            element={element}
            error={snapshot.errors.find((error) => error.element_id === element.id)}
            interactive={canAnnotate}
            onShow={(elementId) => { if (kind !== 'pointer') sendCommand?.(`annotation.${kind}`, { element_id: elementId, label }); }}
            onPointer={kind === 'pointer' ? point : undefined}
            onPointerEnd={kind === 'pointer' ? () => sendCommand?.('annotation.pointer', { visible: false }) : undefined}
          />
        ))}
      </Flex>
      <Button size="small" stretched variant="destructive" onClick={onLeave}>Выйти из помощи</Button>
    </Flex>
  );
}
