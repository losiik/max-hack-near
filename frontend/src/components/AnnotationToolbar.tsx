import { Button, Flex, Typography } from '@maxhub/max-ui';

export type AnnotationKind = 'highlight' | 'frame' | 'circle' | 'arrow' | 'pointer';

const tools: Array<{ kind: AnnotationKind; label: string }> = [
  { kind: 'highlight', label: 'Подсветка' },
  { kind: 'frame', label: 'Рамка' },
  { kind: 'circle', label: 'Круг' },
  { kind: 'arrow', label: 'Стрелка' },
  { kind: 'pointer', label: 'Указка' },
];
const labels = ['Нажмите сюда', 'Заполните поле', 'Проверьте это'];

export function AnnotationToolbar({ kind, label, onKindChange, onLabelChange, onClear }: { kind: AnnotationKind; label: string; onKindChange: (kind: AnnotationKind) => void; onLabelChange: (label: string) => void; onClear: () => void }) {
  return <section className="annotation-toolbar" aria-label="Пометки для владельца">
    <Typography.Label>Покажите, куда смотреть</Typography.Label>
    <div className="annotation-toolbar__scroll"><Flex gap={8}>
      {tools.map((tool) => <Button key={tool.kind} size="small" variant={kind === tool.kind ? 'secondary' : 'ghost'} onClick={() => onKindChange(tool.kind)}>{tool.label}</Button>)}
    </Flex></div>
    {kind !== 'pointer' && <div className="annotation-toolbar__scroll"><Flex gap={8}>
      {labels.map((item) => <Button key={item} size="small" variant={label === item ? 'secondary' : 'ghost'} onClick={() => onLabelChange(item)}>{item}</Button>)}
    </Flex></div>}
    <Button size="small" variant="ghost" onClick={onClear}>Убрать мои пометки</Button>
  </section>;
}
