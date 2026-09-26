import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation } from '@tanstack/react-query';
import { useEffect } from 'react';
import { declineAssistInvite } from '../api/client';
import { ScreenIntro } from '../components/ScreenIntro';
import { StatusScreen } from '../components/UiPrimitives';

export function H5Busy({ token, onReady, onHome }: { token: string; onReady: (callbackId: string) => void; onHome: () => void }) {
  const decline = useMutation({ mutationFn: declineAssistInvite });
  useEffect(() => { if (!decline.isIdle) return; decline.mutate(token); }, [decline, token]);
  if (decline.isPending || decline.isIdle) return <Typography.Text>Сообщаем, что вы сейчас заняты…</Typography.Text>;
  if (decline.error || !decline.data) return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Не удалось обновить статус" description={decline.error instanceof Error ? decline.error.message : 'Попробуйте открыть приглашение ещё раз.'} /><Button size="small" stretched onClick={onHome}>На главную</Button></Flex>;
  return <div className="ui-page centered-screen"><StatusScreen icon="clock" tone="orange" title={`Мы сообщили ${decline.data.owner.display_name}, что вы сейчас заняты`} description="Когда освободитесь — нажмите кнопку, и вас можно будет позвать снова." /><div className="screen-actions"><Button size="small" stretched onClick={() => onReady(decline.data!.help_callback_id)}>Я освободился</Button><Button size="small" stretched variant="ghost" onClick={onHome}>На главную</Button></div></div>;
}
