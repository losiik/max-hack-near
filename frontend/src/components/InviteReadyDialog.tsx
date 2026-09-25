import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { AssistInvite } from '../api/client';
import { shareMaxContent } from '../platform/maxBridge';
import { useToast } from './ToastProvider';
import { AppDialog } from './AppDialog';

function expiryLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? 'ограниченное время' : `до ${date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`;
}

export function InviteReadyDialog({ invite, onClose }: { invite: AssistInvite; onClose: () => void }) {
  const toast = useToast();
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(invite.deep_link);
      toast('Ссылка скопирована');
    } catch {
      toast('Не удалось скопировать ссылку', 'error');
    }
  };
  const share = async () => {
    try {
      await shareMaxContent({ text: invite.share_text, link: invite.deep_link });
      toast('Выберите получателя в MAX');
    } catch {
      toast('Не удалось открыть отправку', 'error');
    }
  };
  return <AppDialog title="Ссылка готова" onClose={onClose} labelledBy="invite-ready-title">
    <Typography.Text>Выберите близкого сами: эта ссылка пока не отправлена конкретному человеку.</Typography.Text>
    <div className="invite-link" aria-label="Ссылка для приглашения">{invite.deep_link}</div>
    <Typography.Text className="muted-text">Ссылка действует {expiryLabel(invite.expires_at)} и откроет помощь только после вашего подтверждения.</Typography.Text>
    <Flex direction="column" gap={8}>
      <Button size="small" stretched onClick={() => void copy()}>Скопировать ссылку</Button>
      <Button size="small" stretched variant="secondary" onClick={() => void share()}>Отправить через MAX</Button>
      <Button size="small" stretched variant="ghost" onClick={onClose}>Продолжить ожидание</Button>
    </Flex>
  </AppDialog>;
}
