import { Button, CellList, CellSimple, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { helpingForQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { openCodeReader } from '../platform/maxBridge';

export function T5HelpingFor({ onOpen, onPairing }: { onOpen: (id: string) => void; onPairing: (token: string) => void }) {
  const list = useQuery({ queryKey: queryKeys.helpingFor(), queryFn: helpingForQuery });
  async function scan() { const value = await openCodeReader(); const match = value?.match(/[?&]startapp=pr_([^&#]+)/); if (match) onPairing(decodeURIComponent(match[1])); }
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Кому я помогаю" description="Здесь показаны люди, которые добавили вас как доверенного помощника." /><Button size="small" stretched variant="secondary" onClick={() => void scan()}>Сканировать QR-код</Button>{list.isLoading && <Typography.Text>Загружаем список…</Typography.Text>}{list.error && <div className="notice notice--error">{list.error instanceof Error ? list.error.message : 'Не удалось загрузить список'}</div>}{list.data?.length === 0 && <Typography.Text className="muted-text">Пока никто не добавил вас как помощника.</Typography.Text>}<CellList mode="island" filled>{list.data?.map((item) => <CellSimple key={item.id} surface="island" title={item.owner.display_name} subtitle={item.active_assist_session_id ? 'Сейчас нужна помощь' : 'Нет активной помощи'} after={item.active_assist_session_id ? <Button size="small" variant="secondary" onClick={() => onOpen(item.active_assist_session_id!)}>Открыть</Button> : undefined} />)}</CellList></Flex>;
}
