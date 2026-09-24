import type { PointerEvent } from 'react';
import { Flex, Panel, Typography } from '@maxhub/max-ui';
import type { FieldError, ProjectedElement } from '../api/client';

interface ProjectedFieldProps {
  element: ProjectedElement;
  error?: FieldError;
  interactive?: boolean;
  onShow?: (elementId: string) => void;
  onPointer?: (elementId: string, event: PointerEvent<HTMLElement>) => void;
  onPointerEnd?: () => void;
}

function publicValue(value: unknown): string {
  if (value === true) return 'Да';
  if (value === false) return 'Нет';
  if (value === null || value === undefined || value === '') return 'Не заполнено';
  return String(value);
}

function ValueView({ element }: { element: ProjectedElement }) {
  if (element.type === 'info') return <Typography.Text>{element.text}</Typography.Text>;
  if (element.type === 'action') {
    return <Typography.Text>{element.action?.available ? element.action.label : '🔒 Отправить заявление может только владелец'}</Typography.Text>;
  }
  if (element.privacy === 'owner_only' || element.view?.locked) {
    return <Typography.Text>🔒 Доступно только владельцу</Typography.Text>;
  }
  if (element.privacy === 'masked') {
    return <Typography.Text>{element.view?.state === 'filled' ? '•••••• · заполнено' : 'Не заполнено'}</Typography.Text>;
  }
  return <Typography.Text>{publicValue(element.view?.value)}</Typography.Text>;
}

export function ProjectedField({ element, error, interactive = false, onShow, onPointer, onPointerEnd }: ProjectedFieldProps) {
  if (element.type === 'summary') {
    return (
      <Panel className="projected-field" data-assist-id={element.id}>
        <Flex direction="column" gap={10}>
          <Typography.Text>{element.label ?? 'Проверка данных'}</Typography.Text>
          {element.rows?.map((row) => (
            <div className="summary-list__row" key={row.element_id}>
              <Typography.Text>{row.label}</Typography.Text>
              <Typography.Text>
                {row.view.locked
                  ? '🔒 Только владельцу'
                  : row.view.state === 'hidden'
                    ? 'Скрыто'
                    : row.view.state === 'filled' && row.view.value === null
                      ? '•••••• · заполнено'
                      : publicValue(row.view.value)}
              </Typography.Text>
            </div>
          ))}
        </Flex>
      </Panel>
    );
  }
  return (
    <Panel
      className={interactive ? 'projected-field projected-field--interactive' : 'projected-field'}
      data-assist-id={element.id}
      onClick={interactive ? () => onShow?.(element.id) : undefined}
      onPointerDown={onPointer ? (event) => { event.currentTarget.setPointerCapture(event.pointerId); onPointer(element.id, event); } : undefined}
      onPointerMove={onPointer ? (event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) onPointer(element.id, event); } : undefined}
      onPointerUp={onPointer ? (event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); onPointerEnd?.(); } : undefined}
      onPointerCancel={onPointerEnd}
    >
      <Flex direction="column" gap={6}>
        <Typography.Text>{element.label ?? element.text ?? 'Поле'}</Typography.Text>
        <ValueView element={element} />
        {error && <Typography.Text className="field-error">{error.message}</Typography.Text>}
      </Flex>
    </Panel>
  );
}
