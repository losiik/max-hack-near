import { useState } from 'react';
import { Button } from '@maxhub/max-ui';
import { AppIcon, AppInput, type AppIconName } from './UiPrimitives';

export type AnnotationKind = 'highlight' | 'pointer';

const tools: Array<{ kind: AnnotationKind; label: string; icon: AppIconName }> = [
  { kind: 'highlight', label: 'Подсветка', icon: 'edit' },
  { kind: 'pointer', label: 'Указка', icon: 'pointer' },
];
const labels = ['Нажмите сюда', 'Выберите это', 'Здесь ошибка'];

function toolLabel(kind: AnnotationKind): string {
  return tools.find((tool) => tool.kind === kind)?.label ?? 'Подсветить';
}

export function AnnotationToolbar({ kind, label, onKindChange, onLabelChange, onClear }: { kind: AnnotationKind; label: string; onKindChange: (kind: AnnotationKind) => void; onLabelChange: (label: string) => void; onClear: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const activeTool = tools.find((tool) => tool.kind === kind) ?? tools[0];
  return <section className={`annotation-toolbar${expanded ? ' is-expanded' : ''}`} aria-label="Инструменты помощника">
    <button type="button" className="annotation-toolbar__toggle" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
      <span className="annotation-toolbar__toggle-copy"><AppIcon name={activeTool.icon} /><span><strong>Инструменты помощника</strong><small>{activeTool.label}</small></span></span>
      <AppIcon name="chevron" className={`annotation-toolbar__chevron${expanded ? ' is-open' : ''}`} />
    </button>
    {expanded && <div className="annotation-toolbar__body">
      <p className="annotation-toolbar__explain"><AppIcon name={activeTool.icon} /><span>{kind === 'pointer' ? 'Проведите пальцем по нужному полю.' : 'Нажмите «Показать» у поля — пометка появится у владельца.'}</span></p>
      <div className="annotation-tools-grid">{tools.map((tool) => <Button key={tool.kind} size="small" variant={kind === tool.kind ? 'secondary' : 'ghost'} aria-pressed={kind === tool.kind} onClick={() => onKindChange(tool.kind)}><AppIcon name={tool.icon} />{tool.label}</Button>)}<Button size="small" variant="ghost" onClick={onClear}><AppIcon name="x" />Убрать</Button></div>
      {kind !== 'pointer' && <><div className="annotation-label-presets">{labels.map((item) => <button type="button" key={item} className={label === item ? 'is-active' : ''} onClick={() => onLabelChange(item)}>{item}</button>)}</div><label className="annotation-label-editor"><span>Своя подпись</span><AppInput maxLength={80} value={label} onChange={(event) => onLabelChange(event.target.value)} placeholder="Например: проверьте адрес" /><small>{label.length}/80</small></label></>}
    </div>}
  </section>;
}
