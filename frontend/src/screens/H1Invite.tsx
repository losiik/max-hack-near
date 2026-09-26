import { Button, Flex, Switch, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { assistInviteQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';

interface H1InviteProps {
  token: string;
  consentRequired: boolean;
  consent: boolean;
  busy: boolean;
  error?: string;
  onConsentChange: (value: boolean) => void;
  onAccept: () => void;
  onBusy: () => void;
  onHome: () => void;
  onOwnerSession: (id: string) => void;
}

export function H1Invite({ token, consentRequired, consent, busy, error, onConsentChange, onAccept, onBusy, onHome, onOwnerSession }: H1InviteProps) {
  const invite = useQuery({ queryKey: queryKeys.assistInvite(token), queryFn: assistInviteQuery, retry: false });
  useEffect(() => {
    if (invite.data?.is_owner) onOwnerSession(invite.data.assist_session_id);
  }, [invite.data, onOwnerSession]);
  if (invite.isLoading) return <Typography.Text>Проверяем приглашение…</Typography.Text>;
  if (invite.error || !invite.data) {
    return <Flex direction="column" gap={16}><ScreenIntro eyebrow="Помощь рядом" title="Приглашение недоступно" description={invite.error instanceof Error ? invite.error.message : 'Не удалось открыть приглашение.'} /><Button variant="ghost" onClick={onHome}>На главную</Button></Flex>;
  }
  const preview = invite.data;
  if (preview.is_owner) {
    return <Typography.Text className="loading-copy">Открываем вашу встречу…</Typography.Text>;
  }
  if (preview.status !== 'valid') {
    return <Flex direction="column" gap={16}><ScreenIntro eyebrow="Помощь рядом" title="Приглашение больше не действует" description="Оно было закрыто или встреча уже завершена." /><Button variant="ghost" onClick={onHome}>На главную</Button></Flex>;
  }
  return (
    <Flex direction="column" gap={12}>
      <ScreenIntro eyebrow={`Шаг ${preview.current_step.index} из ${preview.current_step.total}`} title={`${preview.owner.display_name} нужна помощь`} description={preview.service.title} />
      <div className="privacy-note"><Typography.Text>Вы увидите шаги и сможете говорить с владельцем и показывать, куда нажать. Личные данные и отправка заявления останутся только у владельца.</Typography.Text></div>
      {consentRequired && <label className="switch-field"><span>Я согласен на запись разговора для повторного обращения к помощи.</span><Switch checked={consent} onChange={(event) => onConsentChange(event.target.checked)} /></label>}
      {error && <div className="notice notice--error">{error}</div>}
      <Button size="small" stretched disabled={busy || (consentRequired && !consent)} onClick={onAccept}>{busy ? 'Подключаем…' : 'Подключиться'}</Button>
      <Button variant="destructive" size="small" stretched disabled={busy} onClick={onBusy}>Сейчас занят</Button>
    </Flex>
  );
}
