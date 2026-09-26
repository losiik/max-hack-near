import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { confirmPairing, createPairing, getPairing, renameTrustedHelper, revokeTrustedHelper, type TrustedHelper } from '../api/client';
import { queryKeys, trustedHelpersQuery } from '../api/queries';
import { useToast } from '../components/ToastProvider';
import { ScreenIntro } from '../components/ScreenIntro';
import { QRCodeSVG } from 'qrcode.react';
import { useEffect, useState } from 'react';
import { AppDialog, ConfirmDialog } from '../components/AppDialog';
import { copyText, setQrBrightness } from '../platform/maxBridge';
import { AppIcon, AppInput, IconButton, PersonRow, Surface } from '../components/UiPrimitives';

export function T1TrustedHelpers() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [rename, setRename] = useState<TrustedHelper | null>(null);
  const [alias, setAlias] = useState('');
  const [revoke, setRevoke] = useState<TrustedHelper | null>(null);
  const helpers = useQuery({ queryKey: queryKeys.trustedHelpers(), queryFn: trustedHelpersQuery });
  const pairing = useMutation({ mutationFn: (method: 'qr' | 'link') => createPairing(method) });
  const status = useQuery({ queryKey: ['pairing', pairing.data?.id], queryFn: ({ signal }) => getPairing(pairing.data!.id, signal), enabled: Boolean(pairing.data?.id), refetchInterval: 2_000 });
  const confirm = useMutation({ mutationFn: () => confirmPairing(pairing.data!.id), onSuccess: () => void helpers.refetch() });
  const renameHelper = useMutation({ mutationFn: ({ id, alias: value }: { id: string; alias: string }) => renameTrustedHelper(id, value), onSuccess: () => { setRename(null); void queryClient.invalidateQueries({ queryKey: queryKeys.trustedHelpers() }); } });
  const revokeHelper = useMutation({ mutationFn: revokeTrustedHelper, onSuccess: () => { setRevoke(null); void queryClient.invalidateQueries({ queryKey: queryKeys.trustedHelpers() }); } });
  const copy = async () => {
    if (!pairing.data) return;
    try { await copyText(pairing.data.deep_link); toast('Ссылка для близкого скопирована'); }
    catch { toast('Не удалось скопировать ссылку', 'error'); }
  };
  useEffect(() => { const active = pairing.data?.method === 'qr'; setQrBrightness(active); return () => { if (active) setQrBrightness(false); }; }, [pairing.data?.method]);
  return <div className="ui-page trusted-helpers-screen">
    <ScreenIntro title="Мои близкие" description="Близких можно позвать одним нажатием: им сразу придёт сообщение в MAX." />
    {helpers.isLoading && <Typography.Text>Загружаем список близких…</Typography.Text>}
    {helpers.error && <div className="notice notice--error" role="alert"><Flex direction="column" gap={8}><Typography.Text>{helpers.error instanceof Error ? helpers.error.message : 'Не удалось загрузить список близких.'}</Typography.Text><Button size="small" onClick={() => void helpers.refetch()}>Повторить</Button></Flex></div>}
    {helpers.data?.length === 0 && <Typography.Text className="muted-text">Близких пока нет.</Typography.Text>}
    {helpers.data && helpers.data.length > 0 && <div className="ui-list">{helpers.data.map((item) => <div className="trusted-helper-row" key={item.id}><PersonRow name={item.alias || item.helper.display_name} meta={`Добавлен через ${item.verification_method === 'qr' ? 'QR-код' : 'ссылку'}${item.last_helped_at ? ' · уже помогал' : ''}`} photoUrl={item.helper.photo_url} tone="blue" trailing={<IconButton icon="more" label={`Действия с ${item.alias || item.helper.display_name}`} onClick={() => { setAlias(item.alias || item.helper.display_name); setRename(item); }} />} /></div>)}</div>}
    <Surface tone="blue" className="with-icon"><AppIcon name="shield" /><p>Близкий помогает, не видя ваших личных данных, и не может отправить заявление за вас.</p></Surface>
    {!pairing.data ? <div className="screen-actions"><Button size="small" stretched onClick={() => pairing.mutate('qr')} loading={pairing.isPending}><AppIcon name="qr" />Добавить близкого</Button><Button size="small" stretched variant="secondary" onClick={() => pairing.mutate('link')} loading={pairing.isPending}><AppIcon name="link" />Добавить по ссылке</Button></div> : <div className="pairing-card"><ScreenIntro title={pairing.data.method === 'qr' ? 'Покажите этот код близкому' : 'Отправьте ссылку близкому'} description={pairing.data.method === 'qr' ? 'Пусть откроет MAX и наведёт камеру на код.' : 'После перехода по ссылке вы подтвердите добавление.'} />{pairing.data.method === 'qr' && <div className="qr-card"><QRCodeSVG value={pairing.data.qr_payload} size={232} level="M" includeMargin /></div>}<div className="invite-link">{pairing.data.deep_link}</div><Button size="small" stretched variant="secondary" onClick={() => void copy()}><AppIcon name="link" />Отправить ссылку вместо кода</Button>{status.error && <div className="notice notice--error" role="alert">{status.error instanceof Error ? status.error.message : 'Не удалось проверить состояние приглашения.'}</div>}{status.data?.status === 'claimed' && status.data.claimed_by && <Surface tone="warning"><PersonRow name={`${status.data.claimed_by.display_name} хочет стать вашим помощником`} meta={status.data.claimed_by.max_username ? `@${status.data.claimed_by.max_username}` : undefined} photoUrl={status.data.claimed_by.photo_url} tone="orange" /><Button size="small" stretched onClick={() => confirm.mutate()} loading={confirm.isPending}>Подтвердить</Button></Surface>}{confirm.error && <div className="notice notice--error" role="alert">{confirm.error instanceof Error ? confirm.error.message : 'Не удалось подтвердить близкого.'}</div>}{confirm.isSuccess && <Typography.Text>Близкий добавлен.</Typography.Text>}</div>}
    {pairing.error && <div className="notice notice--error">{pairing.error instanceof Error ? pairing.error.message : 'Не удалось создать ссылку'}</div>}
    {rename && <AppDialog title="Как называть близкого?" onClose={() => !renameHelper.isPending && setRename(null)}><Flex direction="column" gap={12}><AppInput maxLength={40} value={alias} onChange={(event) => setAlias(event.target.value)} aria-label="Имя близкого" /><Button size="small" stretched disabled={!alias.trim() || renameHelper.isPending} onClick={() => renameHelper.mutate({ id: rename.id, alias: alias.trim() })}>Сохранить</Button><Button size="small" stretched variant="destructive" onClick={() => { setRename(null); setRevoke(rename); }}>Удалить близкого</Button></Flex></AppDialog>}
    {revoke && <ConfirmDialog title="Удалить близкого?" description={`${revoke.alias || revoke.helper.display_name} больше не сможет подключаться одним нажатием.`} confirmLabel="Удалить" destructive pending={revokeHelper.isPending} onCancel={() => setRevoke(null)} onConfirm={() => revokeHelper.mutate(revoke.id)} />}
  </div>;
}
