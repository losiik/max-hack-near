import { Button, Flex } from '@maxhub/max-ui';
import { ScreenIntro } from '../components/ScreenIntro';

export function S10HelperBusy({ onSave, onOther }: { onSave: () => void; onOther: () => void }) {
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Помощник сейчас занят" description="Черновик сохранён. Он сможет сообщить, когда освободится, а вы получите уведомление в MAX." /><Button size="small" stretched onClick={onSave}>Сохранить и вернуться</Button><Button size="small" stretched variant="secondary" onClick={onOther}>Позвать другого</Button></Flex>;
}
