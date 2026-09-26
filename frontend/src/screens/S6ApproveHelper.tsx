import { Button } from '@maxhub/max-ui';
import { AppDialog } from '../components/AppDialog';
import { AppIcon, PersonRow } from '../components/UiPrimitives';

interface S6ApproveHelperProps {
  helper: { display_name: string; photo_url: string | null; max_username?: string | null };
  busy: boolean;
  error?: string;
  onApprove: () => void;
  onReject: () => void;
}

export function S6ApproveHelper({ helper, busy, error, onApprove, onReject }: S6ApproveHelperProps) {
  return (
    <AppDialog title={`${helper.display_name} хочет помочь`} onClose={() => { if (!busy) onReject(); }} labelledBy="approve-helper-title">
      <div className="approve-helper">
        <PersonRow large name={helper.display_name} meta={helper.max_username ? `@${helper.max_username} · перешёл по ссылке` : 'Пользователь MAX · перешёл по ссылке'} photoUrl={helper.photo_url} tone="orange" />
        <div className="warning-note"><AppIcon name="warning" /><span>Разрешайте подключение только знакомым лично людям. Если кто-то просит добавить помощника по телефону — это может быть мошенничество.</span></div>
        {error && <div className="notice notice--error">{error}</div>}
        <div className="dialog-actions"><Button size="small" variant="destructive" disabled={busy} onClick={onReject}>Отклонить</Button><Button size="small" disabled={busy} loading={busy} onClick={onApprove}>Разрешить</Button></div>
      </div>
    </AppDialog>
  );
}
