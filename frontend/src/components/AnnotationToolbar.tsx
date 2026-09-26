import { Button, Flex, Input, Typography } from '@maxhub/max-ui';
import { useState } from 'react';
import { AppDialog } from './AppDialog';

export type AnnotationKind = 'highlight' | 'frame' | 'circle' | 'arrow' | 'pointer';

const tools: Array<{ kind: AnnotationKind; label: string }> = [
  { kind: 'highlight', label: 'Подсветить' },
  { kind: 'frame', label: 'Рамка' },
  { kind: 'circle', label: 'Круг' },
  { kind: 'arrow', label: 'Стрелка' },
  { kind: 'pointer', label: 'Указка' },
];
const labels = ['Нажмите сюда', 'Заполните поле', 'Проверьте это'];

function toolLabel(kind: AnnotationKind): string {
  return tools.find((tool) => tool.kind === kind)?.label ?? 'Подсветить';
}

export function AnnotationToolbar({ kind, label, onKindChange, onLabelChange, onClear }: { kind: AnnotationKind; label: string; onKindChange: (kind: AnnotationKind) => void; onLabelChange: (label: string) => void; onClear: () => void }) {
  const [open, setOpen] = useState(false);
  const [editingLabel, setEditingLabel] = useState(Boolean(label));
  const selectedLabel = label.trim();
  return <>
    <section className="annotation-selector" aria-label="Способ подсказки">
      <Button size="small" stretched variant="secondary" onClick={() => setOpen(true)}>
        <span className="annotation-selector__copy"><Typography.Label>Способ подсказки</Typography.Label><Typography.Text>{toolLabel(kind)}{selectedLabel ? ` · «${selectedLabel}»` : ''}</Typography.Text></span>
      </Button>
    </section>
    {open && <AppDialog title="Как показать владельцу?" onClose={() => setOpen(false)} labelledBy="annotation-dialog-title">
      <Typography.Text className="muted-text">Сначала выберите способ. Пометка появится только после нажатия «Показать» у нужного поля.</Typography.Text>
      <div className="annotation-tools-grid">
        {tools.map((tool) => <Button key={tool.kind} size="small" stretched variant={kind === tool.kind ? 'secondary' : 'ghost'} onClick={() => onKindChange(tool.kind)}>{tool.label}</Button>)}
      </div>
      {kind !== 'pointer' && <Flex direction="column" gap={8}>
        {!editingLabel && <Button size="small" variant="ghost" onClick={() => setEditingLabel(true)}>Добавить подпись</Button>}
        {editingLabel && <label className="annotation-label-editor"><Typography.Label>Подпись владельцу</Typography.Label><Input size="medium" maxLength={80} value={label} onChange={(event) => onLabelChange(event.target.value)} placeholder="Например: проверьте адрес" /><Typography.Text className="muted-text">{label.length}/80</Typography.Text><div className="annotation-label-presets">{labels.map((item) => <Button key={item} size="small" variant={label === item ? 'secondary' : 'ghost'} onClick={() => onLabelChange(item)}>{item}</Button>)}</div>{selectedLabel && <Button size="small" variant="ghost" onClick={() => { onLabelChange(''); setEditingLabel(false); }}>Убрать подпись</Button>}</label>}
      </Flex>}
      {kind === 'pointer' && <Typography.Text className="muted-text">После закрытия проведите пальцем по нужному полю.</Typography.Text>}
      <Flex gap={8} className="dialog-actions">
        <Button size="small" variant="ghost" onClick={() => { onClear(); setOpen(false); }}>Убрать мои пометки</Button>
        <Button size="small" onClick={() => setOpen(false)}>Готово</Button>
      </Flex>
    </AppDialog>}
  </>;
}
