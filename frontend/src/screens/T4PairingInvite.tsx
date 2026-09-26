import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery } from '@tanstack/react-query';
import { claimPairing, getPairingPreview } from '../api/client';
import { ScreenIntro } from '../components/ScreenIntro';

export function T4PairingInvite({ token, onHome }: { token: string; onHome: () => void }) {
  const preview = useQuery({ queryKey: ['pairing-token', token], queryFn: ({ signal }) => getPairingPreview(token, signal) });
  const claim = useMutation({ mutationFn: () => claimPairing(token) });
  if (preview.isLoading) return <Typography.Text>Проверяем приглашение…</Typography.Text>;
  if (preview.error || !preview.data || preview.data.status !== 'valid') return <Flex direction="column" gap={12}><ScreenIntro title="Ссылка недоступна" description="Возможно, она уже использована или срок действия закончился." /><Button size="small" stretched onClick={onHome}>На главную</Button></Flex>;
  if (claim.isSuccess) return <Flex direction="column" gap={12}><ScreenIntro title="Готово" description="Теперь дождитесь, пока владелец подтвердит добавление." /><Button size="small" stretched onClick={onHome}>На главную</Button></Flex>;
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title={`${preview.data.owner.display_name} хочет добавить вас`} description="Вы сможете помогать с заявлением, не видя личные данные." />{claim.error && <div className="notice notice--error">{claim.error instanceof Error ? claim.error.message : 'Не удалось принять приглашение'}</div>}<Button size="small" stretched loading={claim.isPending} onClick={() => claim.mutate()}>Принять</Button><Button size="small" stretched variant="ghost" onClick={onHome}>Не сейчас</Button></Flex>;
}
