import { Button } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { confirmPairing, getPairing, rejectPairing } from '../api/client';
import { queryKeys } from '../api/queries';
import { AppIcon, LoadingMessage, PersonRow, StatusScreen, Surface } from '../components/UiPrimitives';

// Открывается кнопкой «Подтвердить» из сообщения бота, когда близкий отсканировал код владельца.
export function T6ConfirmPairing({ pairingId, onHelpers }: { pairingId: string; onHelpers: () => void }) {
  const queryClient = useQueryClient();
  const state = useQuery({ queryKey: ['pairing', pairingId], queryFn: ({ signal }) => getPairing(pairingId, signal), retry: false });
  const confirm = useMutation({ mutationFn: () => confirmPairing(pairingId), onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.trustedHelpers() }) });
  const reject = useMutation({ mutationFn: () => rejectPairing(pairingId) });
  const toHelpers = <div className="screen-actions"><Button size="small" stretched onClick={onHelpers}>К моим близким</Button></div>;

  if (state.isLoading) return <LoadingMessage>Проверяем запрос…</LoadingMessage>;
  if (confirm.isSuccess) return <div className="ui-page centered-screen"><StatusScreen icon="check" tone="green" title="Близкий добавлен" description="Теперь его можно позвать на помощь одним нажатием." />{toHelpers}</div>;
  if (reject.isSuccess) return <div className="ui-page centered-screen"><StatusScreen icon="lock" tone="orange" title="Запрос отклонён" description="Этот человек не добавлен в список близких." />{toHelpers}</div>;
  if (state.error || state.data?.status !== 'claimed' || !state.data.claimed_by) return <div className="ui-page centered-screen"><StatusScreen icon="clock" tone="orange" title="Запрос уже неактуален" description="Его подтвердили, отклонили или истёк срок ответа. Чтобы добавить близкого, покажите ему новый код." />{toHelpers}</div>;

  const claimer = state.data.claimed_by;
  const error = confirm.error ?? reject.error;
  return <div className="ui-page pairing-invite-screen">
    <PersonRow large name={`${claimer.display_name} хочет стать вашим близким`} meta={claimer.max_username ? `@${claimer.max_username}` : 'Доверенный помощник'} photoUrl={claimer.photo_url} tone="orange" />
    <Surface tone="blue" className="with-icon"><AppIcon name="shield" /><p>Близкий сможет помогать с заявлением голосом и подсветкой, но не увидит ваших личных данных и не отправит заявление за вас.</p></Surface>
    {error && <div className="notice notice--error" role="alert">{error instanceof Error ? error.message : 'Не удалось ответить на запрос.'}</div>}
    <div className="screen-actions">
      <Button size="small" stretched loading={confirm.isPending} disabled={reject.isPending} onClick={() => confirm.mutate()}>Подтвердить</Button>
      <Button size="small" stretched variant="ghost" loading={reject.isPending} disabled={confirm.isPending} onClick={() => reject.mutate()}>Это не мой близкий</Button>
    </div>
  </div>;
}
