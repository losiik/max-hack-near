import { Button, Flex, Typography } from '@maxhub/max-ui';
import { ScreenIntro } from '../components/ScreenIntro';

export function H2Pending({ error, rejected = false, connection, onHome }: { error?: string | null; rejected?: boolean; connection?: string; onHome: () => void }) {
  const title = rejected ? 'Подключение отклонено' : 'Ждём подтверждения';
  const description = rejected ? 'Владелец не разрешил подключение. Вы можете вернуться на главную.' : 'Владелец должен разрешить ваше подключение к услуге.';
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title={title} description={description} />{!rejected && <div className="status-hero"><span className="status-mark status-mark--attention" /><Typography.Text>{connection === 'reconnecting' ? 'Восстанавливаем соединение…' : 'Окно обновится автоматически'}</Typography.Text></div>}{error && <div className="notice notice--error">{error}</div>}<Button size="small" variant="ghost" onClick={onHome}>На главную</Button></Flex>;
}
