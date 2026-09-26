import { Flex, Typography } from '@maxhub/max-ui';
import { AppDialog } from '../components/AppDialog';
import { InlineAction } from '../components/InlineAction';
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
    <AppDialog title={`${helper.display_name} хочет помочь`} onClose={() => { if (!busy) onReject(); }} labelledBy="approve-helper-title">
      <Flex direction="column" gap={12}>
        <ScreenIntro eyebrow="Новый помощник" title={helper.max_username ? `@${helper.max_username}` : 'Пользователь MAX'} />
        <div className="warning-note">Разрешайте подключение только знакомым лично людям. Если кто-то просит добавить помощника по телефону — это может быть мошенничество.</div>
        {error && <div className="notice notice--error">{error}</div>}
        <InlineAction title="Разрешить подключение" description="Помощник увидит только доступные ему поля." action="Разрешить" disabled={busy} loading={busy} onClick={onApprove} />
        <InlineAction title="Не разрешать" description="Подключение не состоится." action="Отклонить" variant="destructive" disabled={busy} onClick={onReject} />
      </Flex>
    </AppDialog>
  );
}
