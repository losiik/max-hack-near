import { Button, CellList, CellSimple, Flex, Input, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { helpingForQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { openCodeReader } from '../platform/maxBridge';

export function T5HelpingFor({ onOpen, onPairing }: { onOpen: (id: string) => void; onPairing: (token: string) => void }) {
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [manualLink, setManualLink] = useState('');
  const [manualOpen, setManualOpen] = useState(false);
  const list = useQuery({ queryKey: queryKeys.helpingFor(), queryFn: helpingForQuery });

  function acceptPairing(value: string): void {
    const startParam = extractStartParam(value.trim());
    if (!startParam?.startsWith('pr_') || startParam.length <= 3) {
      setScanError('Нужна ссылка приглашения из приложения «Рядом» с параметром startapp=pr_…');
      return;
    }
    setScanError(null);
    onPairing(startParam.slice(3));
  }

  async function scan() {
    setScanError(null);
    setScanning(true);
    try {
      const value = await openCodeReader();
      if (!value) return;
      acceptPairing(value);
    } catch (reason) {
      setScanError(reason instanceof Error ? reason.message : 'Не удалось отсканировать QR-код.');
    } finally {
      setScanning(false);
    }
  }

  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Кому я помогаю" description="Здесь показаны люди, которые добавили вас как доверенного помощника." /><Button size="small" stretched variant="secondary" loading={scanning} onClick={() => void scan()}>Сканировать QR-код</Button><Button size="small" variant="ghost" onClick={() => { setManualOpen((value) => !value); setScanError(null); }}>Вставить ссылку вручную</Button>{manualOpen && <Flex direction="column" gap={8} className="qr-manual"><Input value={manualLink} onChange={(event) => setManualLink(event.target.value)} placeholder="Ссылка приглашения" aria-label="Ссылка приглашения" /><Button size="small" stretched onClick={() => acceptPairing(manualLink)}>Продолжить</Button></Flex>}{scanError && <div className="notice notice--error" role="alert">{scanError}</div>}{list.isLoading && <Typography.Text>Загружаем список…</Typography.Text>}{list.error && <div className="notice notice--error" role="alert"><Flex direction="column" gap={8}><Typography.Text>{list.error instanceof Error ? list.error.message : 'Не удалось загрузить список'}</Typography.Text><Button size="small" onClick={() => void list.refetch()}>Повторить</Button></Flex></div>}{list.data?.length === 0 && <Typography.Text className="muted-text">Пока никто не добавил вас как помощника.</Typography.Text>}<CellList mode="island" filled>{list.data?.map((item) => <CellSimple key={item.id} surface="island" title={item.owner.display_name} subtitle={item.active_assist_session_id ? 'Сейчас нужна помощь' : 'Нет активной помощи'} after={item.active_assist_session_id ? <Button size="small" variant="secondary" onClick={() => onOpen(item.active_assist_session_id!)}>Открыть</Button> : undefined} />)}</CellList></Flex>;
}

function extractStartParam(value: string): string | null {
  try {
    const url = new URL(value);
    return url.searchParams.get('startapp');
  } catch {
    const match = value.match(/(?:[?&]|^)startapp=([^&#]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  }
}
