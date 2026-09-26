import { Button, Flex, Switch, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { assistInviteQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { AppIcon, PersonRow, Surface } from '../components/UiPrimitives';

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
    <div className="ui-page invite-screen">
      <PersonRow large name={`${preview.owner.display_name} нужна помощь`} meta={preview.service.title} photoUrl={preview.owner.photo_url} tone="green" />
      <Surface tone="blue"><div className="ui-kv"><span>Сейчас</span><strong>Шаг {preview.current_step.index} из {preview.current_step.total} · {preview.current_step.title}</strong></div></Surface>
      <Surface className="invite-capabilities"><h2>Вы сможете</h2><ul className="ui-check-list"><li><AppIcon name="check" />Видеть текущий шаг</li><li><AppIcon name="check" />Говорить голосом</li><li><AppIcon name="check" />Показывать, куда нажать</li></ul><h2>Не сможете</h2><ul className="ui-check-list ui-check-list--muted"><li><AppIcon name="lock" />Видеть СНИЛС, номер счёта и коды</li><li><AppIcon name="lock" />Отправить заявление за владельца</li></ul></Surface>
      {consentRequired && <label className="switch-field recording-consent"><span>Разговор записывается и сохраняется, чтобы к нему можно было вернуться.</span><Switch checked={consent} onChange={(event) => onConsentChange(event.target.checked)} /></label>}
      {error && <div className="notice notice--error">{error}</div>}
      <div className="screen-actions"><Button size="small" stretched disabled={busy || (consentRequired && !consent)} onClick={onAccept}>{busy ? 'Подключаем…' : 'Подключиться'}</Button><Button variant="secondary" size="small" stretched disabled={busy} onClick={onBusy}>Сейчас занят</Button></div>
    </div>
  );
}
