import { Button, Flex, Typography } from '@maxhub/max-ui';
import { ScreenIntro } from '../components/ScreenIntro';

interface S6ApproveHelperProps {
  helper: { display_name: string; photo_url: string | null; max_username?: string | null };
  busy: boolean;
  error?: string;
  onApprove: () => void;
  onReject: () => void;
}

export function S6ApproveHelper({ helper, busy, error, onApprove, onReject }: S6ApproveHelperProps) {
  return (
    <div className="dialog-backdrop" role="presentation">
      <Flex direction="column" gap={14} className="dialog-sheet" role="dialog" aria-modal="true" aria-label="Подтвердить помощника">
        <ScreenIntro eyebrow="Новый помощник" title={`${helper.display_name} хочет помочь`} description={helper.max_username ? `@${helper.max_username}` : 'Пользователь MAX'} />
        <div className="warning-note">Разрешайте подключение только знакомым лично людям. Если кто-то просит добавить помощника по телефону — это может быть мошенничество.</div>
        {error && <div className="notice notice--error">{error}</div>}
        <Button size="small" stretched disabled={busy} onClick={onApprove}>{busy ? 'Подключаем…' : 'Разрешить'}</Button>
        <Button size="small" variant="ghost" disabled={busy} onClick={onReject}>Отклонить</Button>
      </Flex>
    </div>
  );
}
