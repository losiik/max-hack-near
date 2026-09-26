import { Button } from '@maxhub/max-ui';
import { StatusScreen } from '../components/UiPrimitives';

export function H2Pending({ error, rejected = false, connection, onHome }: { error?: string | null; rejected?: boolean; connection?: string; onHome: () => void }) {
  const title = rejected ? 'Подключение отклонено' : 'Ждём подтверждения';
  const description = rejected ? 'Владелец не разрешил подключение. Вы можете вернуться на главную.' : 'Владелец должен разрешить ваше подключение к услуге.';
  return <div className="ui-page centered-screen"><StatusScreen icon={rejected ? 'x' : 'clock'} tone={rejected ? 'red' : 'orange'} title={title} description={description}>{!rejected && <div className="status-meta"><span className="status-mark status-mark--attention" /><span>{connection === 'reconnecting' ? 'Восстанавливаем соединение…' : 'Экран обновится автоматически'}</span></div>}</StatusScreen>{error && <div className="notice notice--error">{error}</div>}<div className="screen-actions"><Button size="small" stretched variant="ghost" onClick={onHome}>На главную</Button></div></div>;
}
