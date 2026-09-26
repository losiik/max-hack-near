import { Radio, Switch, Flex, Typography } from '@maxhub/max-ui';
import type { FieldError, ServiceDefinition, ServiceElement, ServiceStep } from '../api/client';
import { AppIcon, AppInput } from './UiPrimitives';

type FieldValue = string | number | boolean | null;

interface FormRendererProps {
  definition: ServiceDefinition;
  step: ServiceStep;
  values: Record<string, unknown>;
  errors: FieldError[];
  onChange: (elementId: string, value: FieldValue) => void;
  onBlur: () => void;
  showPrivacyHints?: boolean;
}

function isVisible(element: ServiceElement, values: Record<string, unknown>): boolean {
  const condition = element.visible_if;
  if (!condition) return true;
  const value = values[condition.element];
  if (condition.in) return condition.in.includes(value);
  return value === condition.equals;
}

function printableValue(value: unknown): string {
  if (value === true) return 'Да';
  if (value === false) return 'Нет';
  if (value === null || value === undefined || value === '') return 'Не заполнено';
  return String(value);
}

function summaryValue(element: ServiceElement, value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Не заполнено';
  if (element.type === 'checkbox') return value === true ? 'Да' : 'Нет';
  if (element.type === 'select' || element.type === 'radio') {
    const optionLabel = element.options?.find((option) => option.value === value)?.label;
    if (optionLabel) return optionLabel;
    const knownLabels: Record<string, string> = {
      labor_veteran: 'Ветеран труда',
      social_decision: 'Решение органа соцзащиты',
      pensioner: 'Пенсионер по старости',
      disabled: 'Человек с инвалидностью или семья с ребёнком-инвалидом',
      large_family: 'Многодетная семья',
      low_income: 'Малоимущая семья',
      spb: 'Санкт-Петербург',
      msk: 'Москва',
      len_obl: 'Ленинградская область',
      owner: 'Собственник',
      tenant: 'Наниматель по договору соцнайма',
      family_member: 'Член семьи собственника',
      pension: 'Пенсия',
      salary: 'Заработная плата',
      benefits: 'Пособия',
      none: 'Нет дохода',
      bank: 'На банковский счёт',
      post: 'Через почтовое отделение',
    };
    return knownLabels[String(value)] ?? printableValue(value).replaceAll('_', ' ');
  }
  if (element.type === 'date' && typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value.split('-').reverse().join('.');
  const rendered = printableValue(value);
  return element.unit ? `${rendered} ${element.unit}` : rendered;
}

function formatSnils(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 11);
  const first = digits.slice(0, 3);
  const second = digits.slice(3, 6);
  const third = digits.slice(6, 9);
  const last = digits.slice(9, 11);
  return [first, second, third].filter(Boolean).join('-') + (last ? ` ${last}` : '');
}

function PrivacyHint({ element, visible }: { element: ServiceElement; visible: boolean }) {
  if (!visible || !element.privacy || element.privacy === 'public') return null;
  return <small className="privacy-hint"><AppIcon name="lock" />Помощник не видит это значение</small>;
}

export function FormRenderer({ definition, step, values, errors, onChange, onBlur, showPrivacyHints = false }: FormRendererProps) {
  const errorFor = (elementId: string) => errors.find((error) => error.element_id === elementId);
  const currentStepIndex = definition.steps.findIndex((serviceStep) => serviceStep.id === step.id);
  const summaryRows = definition.steps.slice(0, Math.max(0, currentStepIndex)).flatMap((serviceStep) =>
    serviceStep.elements
      .filter((element) => element.label && ['text', 'number', 'date', 'select', 'radio', 'checkbox'].includes(element.type))
      .filter((element) => isVisible(element, values))
      .map((element) => ({ label: element.label!, value: summaryValue(element, values[element.id]) })),
  );

  return (
    <Flex direction="column" gap={16} className="service-fields">
      {step.elements.filter((element) => isVisible(element, values)).map((element) => {
        const error = errorFor(element.id);
        const label = element.label ?? '';
        const value = values[element.id];

        if (element.type === 'info') {
          return (
            <div key={element.id} className={element.style === 'warning' ? 'form-info form-info--warning' : 'form-info'}>
              <AppIcon name={element.style === 'warning' ? 'warning' : 'info'} /><Typography.Text>{element.text}</Typography.Text>
            </div>
          );
        }

        if (element.type === 'summary') {
          return (
            <Flex key={element.id} direction="column" gap={10}>
              <Typography.Title>{label}</Typography.Title>
              <div className="summary-list ui-surface">
                {summaryRows.map((row) => (
                  <div className="summary-list__row" key={row.label}>
                    <Typography.Text>{row.label}</Typography.Text>
                    <Typography.Text>{row.value}</Typography.Text>
                  </div>
                ))}
              </div>
            </Flex>
          );
        }

        if (element.type === 'action') return null;

        if (element.type === 'checkbox') {
          return (
            <label className="switch-field" key={element.id} data-assist-id={element.id}>
              <span>
                {label}
                {element.required ? ' *' : ''}
              </span>
              <Switch
                checked={Boolean(value)}
                onChange={(event) => onChange(element.id, event.target.checked)}
                onBlur={onBlur}
              />
              <PrivacyHint element={element} visible={showPrivacyHints} />
              {error && <small className="field-error">{error.message}</small>}
            </label>
          );
        }

        if (element.type === 'radio') {
          return (
            <fieldset className="option-field" key={element.id} data-assist-id={element.id}>
              <legend>
                {label}
                {element.required ? ' *' : ''}
              </legend>
              <PrivacyHint element={element} visible={showPrivacyHints} />
              <Flex direction="column" gap={12}>
                {element.options?.map((option) => (
                  <label className="radio-option" key={option.value}>
                    <Radio
                      name={element.id}
                      value={option.value}
                      checked={value === option.value}
                      onChange={() => onChange(element.id, option.value)}
                      onBlur={onBlur}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </Flex>
              {element.hint && <small className="field-hint">{element.hint}</small>}
              {error && <small className="field-error">{error.message}</small>}
            </fieldset>
          );
        }

        if (element.type === 'select') {
          return (
            <label className="input-field" key={element.id} data-assist-id={element.id}>
              <span>
                {label}
                {element.required ? ' *' : ''}
              </span>
              <PrivacyHint element={element} visible={showPrivacyHints} />
              <select
                className="max-select"
                value={typeof value === 'string' ? value : ''}
                onChange={(event) => onChange(element.id, event.target.value || null)}
                onBlur={onBlur}
              >
                <option value="">Выберите вариант</option>
                {element.options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {element.hint && <small className="field-hint">{element.hint}</small>}
              {error && <small className="field-error">{error.message}</small>}
            </label>
          );
        }

        const type = element.type === 'otp' ? 'text' : element.type;
        const isSnils = element.id === 'snils';
        const displayedValue = value === null || value === undefined ? '' : String(value);
        return (
          <label className="input-field" key={element.id} data-assist-id={element.id}>
            <span>
              {label}
              {element.required ? ' *' : ''}
            </span>
            <PrivacyHint element={element} visible={showPrivacyHints} />
            <div className={element.unit ? 'input-with-unit' : undefined}>
              <AppInput
                type={type}
                value={isSnils ? formatSnils(displayedValue) : displayedValue}
                placeholder={element.placeholder}
                inputMode={element.type === 'number' || element.type === 'otp' || isSnils ? 'numeric' : undefined}
                maxLength={element.type === 'otp' ? 4 : isSnils ? 14 : undefined}
                onChange={(event) => {
                  const raw = event.target.value;
                  const normalized = isSnils ? formatSnils(raw) : raw;
                  onChange(element.id, element.type === 'number' ? (raw === '' ? null : Number(raw)) : normalized || null);
                }}
                onBlur={onBlur}
              />
              {element.unit && <span className="input-unit" aria-hidden="true">{element.unit}</span>}
            </div>
            {element.hint && <small className="field-hint">{element.hint}</small>}
            {error && <small className="field-error">{error.message}</small>}
          </label>
        );
      })}
    </Flex>
  );
}
