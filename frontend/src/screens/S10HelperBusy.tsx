import { Button } from '@maxhub/max-ui';
import { AppIcon, StatusScreen, Surface } from '../components/UiPrimitives';

export function S10HelperBusy({ onSave, onOther }: { onSave: () => void; onOther: () => void }) {
  return <div className="ui-page centered-screen"><StatusScreen icon="clock" tone="orange" title="Помощник сейчас занят" description="Когда он освободится, мы пришлём сообщение в MAX — вы сможете позвать его одним нажатием." /><Surface className="with-icon"><AppIcon name="check" /><p>Черновик сохранён. Ничего не потеряется.</p></Surface><div className="screen-actions"><Button size="small" stretched onClick={onSave}>Сохранить и вернуться</Button><Button size="small" stretched variant="secondary" onClick={onOther}>Позвать другого</Button></div></div>;
}
