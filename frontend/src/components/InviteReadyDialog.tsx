import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { AssistInvite } from '../api/client';
import { copyText, shareMaxContent } from '../platform/maxBridge';
import { useToast } from './ToastProvider';
import { AppDialog } from './AppDialog';
import { InlineAction } from './InlineAction';

function expiryLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? 'ограниченное время' : `до ${date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`;
}

export function InviteReadyDialog({ invite, onClose }: { invite: AssistInvite; onClose: () => void }) {
  const toast = useToast();
  const copy = async () => {
    try {
      await copyText(invite.deep_link);
      toast('Ссылка скопирована');
    } catch {
      toast('Не удалось скопировать ссылку', 'error');
    }
  };
  const share = async () => {
    try {
      const result = await shareMaxContent({ text: invite.share_text, link: invite.deep_link });
      toast(result === 'clipboard' ? 'Ссылка скопирована — вставьте её в MAX' : result === 'max-web' ? 'MAX открыт, ссылка скопирована — вставьте её в чат' : 'Окно отправки открыто — выберите получателя');
    } catch {
      toast('Не удалось открыть отправку', 'error');
    }
  };
  return <AppDialog title="Ссылка готова" onClose={onClose} labelledBy="invite-ready-title">
    <Typography.Text>Эта ссылка ещё не отправлена конкретному человеку. Получателя выбираете вы.</Typography.Text>
    <div className="invite-link" aria-label="Ссылка для приглашения">{invite.deep_link}</div>
    <Typography.Text className="muted-text">Ссылка действует {expiryLabel(invite.expires_at)} и откроет помощь только после вашего подтверждения.</Typography.Text>
    <Flex direction="column" gap={8}>
      <InlineAction title="Скопировать" description="Вставьте ссылку в любой чат" action="Копировать" onClick={() => void copy()} />
      <InlineAction title="Отправить через MAX" description="Откроется системный выбор получателя" action="Отправить" variant="secondary" onClick={() => void share()} />
      <Button size="small" stretched variant="ghost" onClick={onClose}>Продолжить ожидание</Button>
    </Flex>
  </AppDialog>;
}
