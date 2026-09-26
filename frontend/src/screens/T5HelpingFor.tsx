import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { helpingForQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { openCodeReader } from '../platform/maxBridge';
import { AppIcon, AppInput, PersonRow, Surface } from '../components/UiPrimitives';

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

  return <div className="ui-page helping-for-screen"><ScreenIntro title="Кому я помогаю" description="Люди, которые добавили вас как доверенного помощника." /><div className="screen-actions"><Button size="small" stretched variant="secondary" loading={scanning} onClick={() => void scan()}><AppIcon name="scan" />Сканировать QR-код</Button><Button size="small" stretched variant="ghost" onClick={() => { setManualOpen((value) => !value); setScanError(null); }}><AppIcon name="link" />Вставить ссылку вручную</Button></div>{manualOpen && <Surface className="qr-manual"><AppInput value={manualLink} onChange={(event) => setManualLink(event.target.value)} placeholder="Ссылка приглашения" aria-label="Ссылка приглашения" /><Button size="small" stretched onClick={() => acceptPairing(manualLink)}>Продолжить</Button></Surface>}{scanError && <div className="notice notice--error" role="alert">{scanError}</div>}{list.isLoading && <Typography.Text>Загружаем список…</Typography.Text>}{list.error && <div className="notice notice--error" role="alert"><Flex direction="column" gap={8}><Typography.Text>{list.error instanceof Error ? list.error.message : 'Не удалось загрузить список'}</Typography.Text><Button size="small" onClick={() => void list.refetch()}>Повторить</Button></Flex></div>}{list.data?.length === 0 && <Surface tone="blue" className="with-icon"><AppIcon name="people" /><p>Пока никто не добавил вас как помощника.</p></Surface>}{list.data && list.data.length > 0 && <div className="ui-list">{list.data.map((item) => <div className="helping-for-row" key={item.id}><PersonRow name={item.owner.display_name} meta={item.active_assist_session_id ? 'Сейчас нужна помощь' : 'Нет активной помощи'} photoUrl={item.owner.photo_url} tone={item.active_assist_session_id ? 'green' : 'blue'} online={Boolean(item.active_assist_session_id)} trailing={item.active_assist_session_id ? <Button size="small" variant="secondary" onClick={() => onOpen(item.active_assist_session_id!)}>Открыть</Button> : undefined} /></div>)}</div>}</div>;
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
