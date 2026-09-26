import { useEffect, useRef, useState } from 'react';
import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ApiError,
  issueConfirmationCode,
  navigateService,
  submitService,
  type ServiceSession,
  type SubmitResult,
} from '../api/client';
import { cacheSession, demoInboxQuery, queryKeys } from '../api/queries';
import { setScreenCaptureProtection } from '../platform/maxBridge';
import { ScreenIntro } from '../components/ScreenIntro';
import { useToast } from '../components/ToastProvider';
import { AppIcon, AppInput } from '../components/UiPrimitives';

interface S7ConfirmationProps {
  session: ServiceSession;
  onBack: (session: ServiceSession) => void;
  onSubmitted: (result: SubmitResult) => void;
}

export function S7Confirmation({ session, onBack, onSubmitted }: S7ConfirmationProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const codeRequestedFor = useRef('');
  const lastMessageId = useRef('');
  const inbox = useQuery({
    queryKey: queryKeys.demoInbox(session.id),
    queryFn: demoInboxQuery,
    retry: false,
  });
  const { mutateAsync: issueCode } = useMutation({ mutationFn: issueConfirmationCode });
  const { mutateAsync: navigateBack, isPending: isNavigatingBack } = useMutation({
    mutationFn: () => navigateService(session.id, 'back'),
    onSuccess: (next) => cacheSession(queryClient, next),
  });
  const { mutateAsync: submit, isPending: isSubmitting } = useMutation({
    mutationFn: (confirmationCode: string) => submitService(session.id, confirmationCode),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: queryKeys.session(session.id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions() });
    },
  });
  const messages = inbox.data ?? [];
  const busy = isNavigatingBack || isSubmitting;

  useEffect(() => {
    setScreenCaptureProtection(true);
    return () => setScreenCaptureProtection(false);
  }, []);

  useEffect(() => {
    if (!inbox.isSuccess || messages.length || codeRequestedFor.current === session.id) return;
    codeRequestedFor.current = session.id;
    let active = true;

    void issueCode(session.id)
      .catch((reason) => {
        if (!(reason instanceof ApiError && reason.status === 429)) throw reason;
      })
      .then(() => queryClient.refetchQueries({ queryKey: queryKeys.demoInbox(session.id) }))
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Не удалось получить код');
      });

    return () => {
      active = false;
    };
  }, [inbox.isSuccess, issueCode, messages.length, queryClient, session.id]);

  useEffect(() => {
    const latest = messages.at(-1);
    if (!latest || latest.id === lastMessageId.current) return;
    lastMessageId.current = latest.id;
    toast(latest.text);
  }, [messages, toast]);

  async function sendApplication() {
    setError('');
    try {
      onSubmitted(await submit(code));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось отправить заявление');
    }
  }

  async function goBack() {
    setError('');
    try {
      onBack(await navigateBack());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось вернуться к проверке');
    }
  }

  return (
    <Flex direction="column" gap={12} className="confirmation-screen">
      <ScreenIntro eyebrow="Шаг 7 из 7" title="Подтверждение и отправка" description="Подтвердите заявление кодом из SMS." />
      <div className="progress-track"><span style={{ width: '100%' }} /></div>
      <div className="warning-note">
        <AppIcon name="warning" /><span>Мы отправили код в SMS. Никому не сообщайте его — ни помощнику, ни сотруднику МФЦ.</span>
      </div>
      {messages.length > 0 && <Button size="small" variant="ghost" onClick={() => toast(messages.at(-1)?.text ?? '')}>Показать демо-SMS</Button>}
      {(error || inbox.error) && <div className="notice notice--error">{error || (inbox.error instanceof Error ? inbox.error.message : 'Не удалось получить код')}</div>}
      <label className="input-field">
        <span>Код из SMS</span>
        <AppInput
          value={code}
          maxLength={4}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="0000"
          onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
        />
      </label>
      <Flex gap={12} className="form-actions screen-actions--row">
        <Button size="small" variant="secondary" disabled={busy} onClick={() => void goBack()}>
          Назад
        </Button>
        <Button size="small" disabled={busy || code.length !== 4} onClick={() => void sendApplication()}>
          Отправить заявление
        </Button>
      </Flex>
    </Flex>
  );
}
