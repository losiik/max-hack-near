import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation } from '@tanstack/react-query';
import { useEffect } from 'react';
import { markHelpCallbackReady } from '../api/client';
import { ScreenIntro } from '../components/ScreenIntro';
import { StatusScreen } from '../components/UiPrimitives';

export function H6Ready({ callbackId, onHome }: { callbackId: string; onHome: () => void }) {
  const ready = useMutation({ mutationFn: markHelpCallbackReady });
  useEffect(() => { if (!ready.isIdle) return; ready.mutate(callbackId); }, [callbackId, ready]);
  if (ready.isPending || ready.isIdle) return <Typography.Text>Сообщаем, что вы готовы помочь…</Typography.Text>;
  if (ready.error) return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Ожидание уже закрыто" description="Возможно, человеку уже помогли или приглашение устарело." /><Button size="small" stretched onClick={onHome}>На главную</Button></Flex>;
  return <div className="ui-page centered-screen"><StatusScreen icon="check" tone="green" title="Человек узнает, что вы готовы помочь" description="Когда вас позовут, в MAX придёт новое приглашение с кнопкой «Подключиться»." /><div className="screen-actions"><Button size="small" stretched onClick={onHome}>На главную</Button></div></div>;
}
