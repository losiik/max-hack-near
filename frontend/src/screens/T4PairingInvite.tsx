import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery } from '@tanstack/react-query';
import { claimPairing, getPairingPreview } from '../api/client';
import { ScreenIntro } from '../components/ScreenIntro';
import { AppIcon, PersonRow, StatusScreen, Surface } from '../components/UiPrimitives';

export function T4PairingInvite({ token, onHome }: { token: string; onHome: () => void }) {
  const preview = useQuery({ queryKey: ['pairing-token', token], queryFn: ({ signal }) => getPairingPreview(token, signal) });
  const claim = useMutation({ mutationFn: () => claimPairing(token) });
  if (preview.isLoading) return <Typography.Text>Проверяем приглашение…</Typography.Text>;
  if (preview.error || !preview.data || preview.data.status !== 'valid') return <Flex direction="column" gap={12}><ScreenIntro title="Ссылка недоступна" description="Возможно, она уже использована или срок действия закончился." /><Button size="small" stretched onClick={onHome}>На главную</Button></Flex>;
  if (claim.isSuccess) return <div className="ui-page centered-screen"><StatusScreen icon="check" tone="green" title="Готово" description="Теперь дождитесь, пока владелец подтвердит добавление." /><div className="screen-actions"><Button size="small" stretched onClick={onHome}>На главную</Button></div></div>;
  return <div className="ui-page pairing-invite-screen"><PersonRow large name={`${preview.data.owner.display_name} хочет добавить вас`} meta="Доверенный помощник" photoUrl={preview.data.owner.photo_url} tone="green" /><Surface tone="blue" className="with-icon"><AppIcon name="shield" /><p>Вы сможете помогать с заявлением, говорить голосом и показывать, куда нажать — личные данные останутся скрыты.</p></Surface>{claim.error && <div className="notice notice--error">{claim.error instanceof Error ? claim.error.message : 'Не удалось принять приглашение'}</div>}<div className="screen-actions"><Button size="small" stretched loading={claim.isPending} onClick={() => claim.mutate()}>Принять</Button><Button size="small" stretched variant="ghost" onClick={onHome}>Не сейчас</Button></div></div>;
}
