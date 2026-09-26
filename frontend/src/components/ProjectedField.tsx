import type { PointerEvent } from 'react';
import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { FieldError, ProjectedElement } from '../api/client';
import { AppIcon } from './UiPrimitives';

interface ProjectedFieldProps {
  element: ProjectedElement;
  error?: FieldError;
  interactive?: boolean;
  confusion?: boolean;
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

function ChoiceView({ element }: { element: ProjectedElement }) {
  const selected = element.view?.value;
  return <div className="projected-choice-list" aria-label="Варианты ответа">
    {element.options?.map((option) => {
      const isSelected = selected !== null && selected !== undefined && String(option.value) === String(selected);
      return <div className={`projected-choice${isSelected ? ' is-selected' : ''}`} key={option.value}>
        <span className="projected-choice__mark">{isSelected && <AppIcon name="check" />}</span>
        <span>{option.label}</span>
      </div>;
    })}
    {selected === null || selected === undefined ? <span className="projected-choice__empty">Ничего не выбрано</span> : null}
  </div>;
}

function ValueView({ element }: { element: ProjectedElement }) {
  if (element.type === 'info') return <Typography.Text>{element.text}</Typography.Text>;
  if (element.type === 'action') {
    return <Typography.Text>{element.action?.available ? element.action.label : <span className="projected-field__locked"><AppIcon name="lock" />Отправить заявление может только владелец</span>}</Typography.Text>;
  }
  if (element.privacy === 'owner_only' || element.view?.locked) {
    return <span className="projected-field__locked"><AppIcon name="lock" />Доступно только владельцу</span>;
  }
  if (element.privacy === 'masked') {
    return <span className="projected-field__masked"><span>████████</span><span className={element.view?.state === 'filled' ? 'is-filled' : ''}>{element.view?.state === 'filled' && <AppIcon name="check" />}{element.view?.state === 'filled' ? 'заполнено' : 'не заполнено'}</span></span>;
  }
  if ((element.type === 'select' || element.type === 'radio') && element.options?.length) return <ChoiceView element={element} />;
  return <Typography.Text>{publicValue(element.view?.value)}</Typography.Text>;
}

export function ProjectedField({ element, error, interactive = false, confusion = false, onShow, onPointer, onPointerEnd }: ProjectedFieldProps) {
  if (element.type === 'summary') {
    return (
      <div className="projected-field" data-assist-id={element.id}>
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
      </div>
    );
  }
  return (
    <div
      className={`projected-field${interactive ? ' projected-field--interactive' : ''}${confusion ? ' projected-field--confusion' : ''}`}
      data-assist-id={element.id}
      onPointerDown={onPointer ? (event) => { event.currentTarget.setPointerCapture(event.pointerId); onPointer(element.id, event); } : undefined}
      onPointerMove={onPointer ? (event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) onPointer(element.id, event); } : undefined}
      onPointerUp={onPointer ? (event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); onPointerEnd?.(); } : undefined}
      onPointerCancel={onPointerEnd}
    >
      <Flex direction="column" gap={6}>
        <Typography.Text>{element.label ?? element.text ?? 'Поле'}</Typography.Text>
        {confusion && <span className="projected-field__confusion">Владельцу здесь непонятно</span>}
        <ValueView element={element} />
        {error && <Typography.Text className="field-error">{error.message}</Typography.Text>}
        {interactive && !onPointer && <div className="projected-field__action"><Button size="small" variant="secondary" onClick={() => onShow?.(element.id)}>Показать</Button></div>}
        {interactive && onPointer && <Typography.Text className="muted-text">Ведите пальцем по полю — владелец увидит указку.</Typography.Text>}
      </Flex>
    </div>
  );
}
