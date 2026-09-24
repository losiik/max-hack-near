import { Button, Flex, Typography } from '@maxhub/max-ui';
import { ScreenIntro } from '../components/ScreenIntro';

export function H2Pending({ error, onHome }: { error?: string | null; onHome: () => void }) {
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Ждём подтверждения" description="Владелец должен разрешить ваше подключение к услуге." />{error && <div className="notice notice--error">{error}</div>}<Button size="small" variant="ghost" onClick={onHome}>На главную</Button></Flex>;
}
