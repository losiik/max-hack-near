import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation } from '@tanstack/react-query';
import { useEffect } from 'react';
import { declineAssistInvite } from '../api/client';
import { ScreenIntro } from '../components/ScreenIntro';

export function H5Busy({ token, onReady, onHome }: { token: string; onReady: (callbackId: string) => void; onHome: () => void }) {
  const decline = useMutation({ mutationFn: declineAssistInvite });
  useEffect(() => { if (!decline.isIdle) return; decline.mutate(token); }, [decline, token]);
  if (decline.isPending || decline.isIdle) return <Typography.Text>Сообщаем, что вы сейчас заняты…</Typography.Text>;
  if (decline.error || !decline.data) return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Не удалось обновить статус" description={decline.error instanceof Error ? decline.error.message : 'Попробуйте открыть приглашение ещё раз.'} /><Button size="small" stretched onClick={onHome}>На главную</Button></Flex>;
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Мы сообщили, что вы заняты" description={`Когда освободитесь, отметьте это здесь — ${decline.data.owner.display_name} сможет позвать вас снова.`} /><Button size="small" stretched onClick={() => onReady(decline.data!.help_callback_id)}>Освободился</Button><Button size="small" stretched variant="secondary" onClick={onHome}>На главную</Button></Flex>;
}
