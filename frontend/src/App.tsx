import { useEffect, useMemo, useState } from 'react';
import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { acceptAssistInvite, agreeToRecording, ApiError, approveAssistParticipant, callDigitalEmployee, createAssistInvite, createAssistSession, endAssistSession, leaveAssistSession, loginWithMax, rejectAssistParticipant, releaseDigitalEmployee, requestOperatorForApplication, startServiceSession, type AssistInvite, type AssistSession, type AuthUser, type ServiceDefinition, type ServiceSession, type ServiceSummary, type SubmitResult } from './api/client';
import { InviteReadyDialog } from './components/InviteReadyDialog';
import { ConfirmDialog } from './components/AppDialog';
import { activeAssistsQuery, assistQuery, assistStateQuery, cacheAssistSession, cacheSession, queryKeys, serviceQuery, sessionQuery } from './api/queries';
import { AppShell } from './app/AppShell';
import { A0 } from './screens/A0';
import { D1 } from './screens/D1';
import { H1Invite } from './screens/H1Invite';
import { H2Pending } from './screens/H2Pending';
import { H3Helper } from './screens/H3Helper';
import { Home } from './screens/Home';
import { S2ServiceCard } from './screens/S2ServiceCard';
import { S3Form } from './screens/S3Form';
import { S4HelpOptions } from './screens/S4HelpOptions';
import { S5Waiting } from './screens/S5Waiting';
import { S6ApproveHelper } from './screens/S6ApproveHelper';
import { S7Confirmation } from './screens/S7Confirmation';
import { S8Submitted } from './screens/S8Submitted';
import { S9Ended } from './screens/S9Ended';
import { O1OperatorQueue } from './screens/O1OperatorQueue';
import { T1TrustedHelpers } from './screens/T1TrustedHelpers';
import { T4PairingInvite } from './screens/T4PairingInvite';
import { T5HelpingFor } from './screens/T5HelpingFor';
import { R1Consultations } from './screens/R1Consultations';
import { R2Consultation } from './screens/R2Consultation';
import { R3Replay } from './screens/R3Replay';
import { H5Busy } from './screens/H5Busy';
import { H6Ready } from './screens/H6Ready';
import { S10HelperBusy } from './screens/S10HelperBusy';
import { getDisplayNameHint, getInitData, getStartParam, isMaxRuntime } from './platform/maxBridge';
import { parseStartParam, type LaunchIntent } from './platform/startParam';
import { useAssistStore } from './realtime/assistStore';
import { useAssistSocket } from './realtime/useAssistSocket';
import { BottomNav } from './components/UiPrimitives';

type AppMode = 'loading' | 'dev' | 'home' | 'operator-queue' | 'trusted-helpers' | 'helping-for' | 'pairing-invite' | 'consultations' | 'consultation-detail' | 'replay' | 'service' | 'form' | 'confirmation' | 'submitted' | 'help-options' | 'waiting' | 'helper-invite' | 'helper-busy' | 'helper-ready' | 'helper-pending' | 'helper-active' | 'assist-busy' | 'assist-ended' | 'error';

export default function App() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<AppMode>('loading');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState('');
  const [launchIntent, setLaunchIntent] = useState<LaunchIntent>({ kind: 'home' });
  const [definition, setDefinition] = useState<ServiceDefinition | null>(null);
  const [draft, setDraft] = useState<ServiceSession>();
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [assist, setAssist] = useState<AssistSession | null>(null);
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [inviteReady, setInviteReady] = useState<AssistInvite | null>(null);
  const [consentRequired, setConsentRequired] = useState(false);
  const [assistError, setAssistError] = useState('');
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [backAction, setBackAction] = useState<'helper' | 'owner' | null>(null);
  const maxUserHint = useMemo(getDisplayNameHint, []);
  const realtime = useAssistStore();
  useAssistSocket(assist?.id ?? null);
  const helperState = useQuery({
    queryKey: queryKeys.assistState(assist?.id ?? ''),
    queryFn: assistStateQuery,
    enabled: mode === 'helper-active' && Boolean(assist?.id),
    retry: false,
  });
  const startSession = useMutation({ mutationFn: startServiceSession, onSuccess: (session) => cacheSession(queryClient, session) });
  const createAssist = useMutation({ mutationFn: createAssistSession, onSuccess: (session) => cacheAssistSession(queryClient, session) });

  function beginUserSession(nextUser: AuthUser) {
    queryClient.clear();
    useAssistStore.getState().reset();
    setUser(nextUser);
  }

  useEffect(() => {
    const intent = parseStartParam(getStartParam());
    setLaunchIntent(intent);
    if (!isMaxRuntime()) {
      if (import.meta.env.DEV) setMode('dev');
      else { setError('Откройте приложение из MAX, чтобы войти и продолжить оформление.'); setMode('error'); }
      return;
    }
    loginWithMax(getInitData()).then(async (response) => {
      beginUserSession(response.user);
      if (intent.kind === 'assist_invite') { setInviteToken(intent.token); setMode('helper-invite'); }
      else if (intent.kind === 'invite_declined') { setInviteToken(intent.token); setMode('helper-busy'); }
      else if (intent.kind === 'helper_ready') { setInviteToken(intent.callbackId); setMode('helper-ready'); }
      else if (intent.kind === 'pairing') { setInviteToken(intent.token); setMode('pairing-invite'); }
      else await restoreActiveAssist();
    }).catch((reason: Error) => { setError(reason.message); setMode('error'); });
  }, []);

  useEffect(() => {
    if (mode === 'helper-pending' && realtime.snapshot) setMode('helper-active');
    if (mode === 'waiting' && assist?.me?.role === 'owner' && realtime.snapshot?.session.status === 'active') setMode('form');
    if (mode === 'waiting' && realtime.inviteDeclined) setMode('assist-busy');
    if (realtime.endedReason && assist && mode !== 'assist-ended') setMode('assist-ended');
  }, [assist, mode, realtime.endedReason, realtime.inviteDeclined, realtime.snapshot]);

  useEffect(() => {
    if (realtime.joinRequest) setInviteReady(null);
  }, [realtime.joinRequest]);

  if (mode === 'loading') return <AppShell><A0 message={maxUserHint ? `Входим как ${maxUserHint}` : undefined} /></AppShell>;
  if (mode === 'dev') return <AppShell><D1 onLogin={beginUserSession} onHome={() => setMode('home')} onLaunch={(value) => { const intent = parseStartParam(value); if (intent.kind === 'assist_invite') { setInviteToken(intent.token); setMode('helper-invite'); } else if (intent.kind === 'invite_declined') { setInviteToken(intent.token); setMode('helper-busy'); } else if (intent.kind === 'helper_ready') { setInviteToken(intent.callbackId); setMode('helper-ready'); } else if (intent.kind === 'pairing') { setInviteToken(intent.token); setMode('pairing-invite'); } }} /></AppShell>;
  if (mode === 'error') return <AppShell><Flex direction="column" gap={12}><Typography.Title>Не удалось продолжить</Typography.Title><Typography.Text>{error || 'Откройте приложение из MAX и попробуйте снова.'}</Typography.Text><Button onClick={() => window.location.reload()}>Повторить</Button></Flex></AppShell>;

  async function openActiveAssist(assistId: string) {
    setMode('loading');
    setError('');
    try {
      const fullAssist = await queryClient.fetchQuery({ queryKey: queryKeys.assist(assistId), queryFn: assistQuery, staleTime: 0 });
      if (fullAssist.status === 'ended') {
        await queryClient.invalidateQueries({ queryKey: queryKeys.activeAssists() });
        setAssist(null);
        setMode('home');
        return;
      }
      setAssist(fullAssist);
      if (fullAssist.me.role === 'owner') {
        if (!fullAssist.service_session_id) throw new Error('У активной помощи нет связанного заявления.');
        const [nextDraft, nextDefinition] = await Promise.all([
          queryClient.fetchQuery({ queryKey: queryKeys.session(fullAssist.service_session_id), queryFn: sessionQuery, staleTime: 0 }),
          queryClient.fetchQuery({ queryKey: queryKeys.service(fullAssist.service.code), queryFn: serviceQuery, staleTime: 30_000 }),
        ]);
        cacheSession(queryClient, nextDraft);
        setDraft(nextDraft);
        setDefinition(nextDefinition);
        if (fullAssist.status === 'active') setMode('form');
        else if (fullAssist.status === 'waiting') setMode('waiting');
        else {
          await queryClient.invalidateQueries({ queryKey: queryKeys.activeAssists() });
          setAssist(null);
          setMode('home');
        }
      } else {
        if (fullAssist.me.status === 'active') setMode('helper-active');
        else if (fullAssist.me.status === 'pending') setMode('helper-pending');
        else {
          await queryClient.invalidateQueries({ queryKey: queryKeys.activeAssists() });
          setAssist(null);
          setMode('home');
        }
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось восстановить помощь.');
      setMode('home');
    }
  }

  async function restoreActiveAssist() {
    try {
      const active = await queryClient.fetchQuery({ queryKey: queryKeys.activeAssists(), queryFn: activeAssistsQuery, staleTime: 0 });
      if (active.length === 1) {
        await openActiveAssist(active[0].id);
      } else {
        setMode('home');
      }
    } catch {
      // Home renders the query error and offers a retry; login itself should remain usable.
      setMode('home');
    }
  }

  async function openService(service: ServiceSummary, existingDraft?: ServiceSession) {
    setMode('loading'); setError('');
    try {
      setDefinition(await queryClient.fetchQuery({ queryKey: queryKeys.service(service.code), queryFn: serviceQuery, staleTime: 30_000 }));
      setDraft(existingDraft); setMode('service');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось открыть услугу'); setMode('error'); }
  }
  async function beginService() {
    if (!definition) return;
    setMode('loading'); setError('');
    try { const next = await startSession.mutateAsync(definition.code); setDraft(next); setMode(next.current_step.id === 'confirmation' ? 'confirmation' : 'form'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось начать оформление'); setMode('error'); }
  }
  async function createAndShare() {
    if (!draft) return;
    setAssistError('');
    try {
      if (consentRequired && consent) await agreeToRecording();
      const nextAssist = assist && assist.status !== 'ended'
        ? assist
        : await createAssist.mutateAsync(draft.id);
      const invite = await createAssistInvite(nextAssist.id);
      setAssist(nextAssist);
      setMode('waiting');
      setInviteReady(invite);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'recording_consent_required') { setConsentRequired(true); setAssistError('Перед приглашением подтвердите согласие на запись разговора.'); }
      else setAssistError(reason instanceof Error ? reason.message : 'Не удалось подготовить приглашение.');
    }
  }
  async function callTrusted(trustedHelperId: string) {
    if (!draft) return;
    setAssistError('');
    try {
      if (consentRequired && consent) await agreeToRecording();
      const nextAssist = assist ?? await createAssist.mutateAsync(draft.id);
      const invite = await createAssistInvite(nextAssist.id, trustedHelperId);
      setAssist(nextAssist);
      setMode('waiting');
      if (invite.delivery === 'share_required') setInviteReady(invite);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'recording_consent_required') { setConsentRequired(true); setAssistError('Перед приглашением подтвердите согласие на запись.'); }
      else setAssistError(reason instanceof Error ? reason.message : 'Не удалось позвать близкого.');
    }
  }
  async function shareAgain() {
    if (!assist) return;
    setAssistError('');
    try { const invite = await createAssistInvite(assist.id); setInviteReady(invite); }
    catch (reason) { setAssistError(reason instanceof Error ? reason.message : 'Не удалось отправить ссылку.'); }
  }
  async function requestOperator(topic: 'dont_understand' | 'form_error' | 'other') {
    if (!draft) return;
    setAssistError('');
    try {
      if (consentRequired && consent) await agreeToRecording();
      const result = await requestOperatorForApplication(draft.id, topic);
      cacheAssistSession(queryClient, result.assist_session);
      setAssist(result.assist_session);
      setMode('waiting');
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'recording_consent_required') { setConsentRequired(true); setAssistError('Перед подключением специалиста подтвердите согласие на запись.'); }
      else setAssistError(reason instanceof Error ? reason.message : 'Не удалось вызвать специалиста.');
    }
  }
  async function callAgent() {
    if (!draft) return;
    setAssistError('');
    try {
      if (consentRequired && consent) await agreeToRecording();
      const result = await callDigitalEmployee(draft.id);
      cacheAssistSession(queryClient, result.assist_session); setAssist(result.assist_session); setMode('form');
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'recording_consent_required') { setConsentRequired(true); setAssistError('Перед разговором подтвердите согласие на запись.'); }
      else setAssistError(reason instanceof Error ? reason.message : 'Цифровой сотрудник недоступен. Позовите близкого или сотрудника МФЦ.');
    }
  }
  async function releaseAgent() { if (!assist) return; try { await releaseDigitalEmployee(assist.id); } catch (reason) { setAssistError(reason instanceof Error ? reason.message : 'Не удалось отпустить цифрового сотрудника.'); } }
  async function finishAssist() {
    if (!assist) return;
    try {
      await endAssistSession(assist.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.activeAssists() });
      await queryClient.invalidateQueries({ queryKey: queryKeys.assist(assist.id) });
      setMode('assist-ended');
    }
    catch (reason) { setAssistError(reason instanceof Error ? reason.message : 'Не удалось завершить помощь.'); }
  }
  async function openHistory() {
    setBackAction(null);
    useAssistStore.getState().reset();
    setAssist(null);
    setMode('consultations');
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.consultations('owner') }),
      queryClient.invalidateQueries({ queryKey: queryKeys.consultations('helper') }),
    ]);
  }
  function continueAfterAssist() {
    // Сбрасываем endedReason до смены режима, иначе realtime-эффект мгновенно вернёт экран завершения.
    useAssistStore.getState().reset();
    setAssist(null);
    setMode(draft ? 'form' : 'home');
  }
  async function approveJoin(approved: boolean) {
    if (!assist || !realtime.joinRequest) return;
    setAssistError('');
    setApprovalBusy(true);
    try {
      const next = approved ? await approveAssistParticipant(assist.id, realtime.joinRequest.id) : await rejectAssistParticipant(assist.id, realtime.joinRequest.id);
      cacheAssistSession(queryClient, next); setAssist(next); setInviteReady(null); useAssistStore.getState().clearJoinRequest();
      if (approved) setMode('form');
    } catch (reason) { setAssistError(reason instanceof Error ? reason.message : 'Не удалось обновить подключение.'); }
    finally { setApprovalBusy(false); }
  }
  async function acceptInvite() {
    if (!inviteToken) return;
    setAssistError('');
    try {
      if (consentRequired && consent) await agreeToRecording();
      const accepted = await acceptAssistInvite(inviteToken);
      setAssist({ id: accepted.assist_session_id } as AssistSession);
      setMode(accepted.status === 'active' ? 'helper-active' : 'helper-pending');
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === 'recording_consent_required') { setConsentRequired(true); setAssistError('Перед подключением подтвердите согласие на запись разговора.'); }
      else setAssistError(reason instanceof Error ? reason.message : 'Не удалось подключиться.');
    }
  }
  async function leaveAssist() {
    if (!assist) return;
    try {
      await leaveAssistSession(assist.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.activeAssists() });
      queryClient.removeQueries({ queryKey: queryKeys.assist(assist.id) });
      setBackAction(null);
      useAssistStore.getState().reset();
      setAssist(null);
      setMode('home');
    }
    catch (reason) { setAssistError(reason instanceof Error ? reason.message : 'Не удалось выйти из помощи.'); }
  }
  const backToHome = () => { setBackAction(null); useAssistStore.getState().reset(); setAssist(null); setMode('home'); };
  const shellBack = mode === 'home' ? undefined : () => {
    if (mode === 'helper-active') setBackAction('helper');
    else if (mode === 'form' && (assist?.status === 'active' || realtime.snapshot?.session.status === 'active')) setBackAction('owner');
    else backToHome();
  };
  if (!user) return null;

  const helperSnapshot = realtime.snapshot ?? helperState.data;
  const shellTitle: Partial<Record<AppMode, string>> = {
    service: 'Услуга', form: definition?.title ?? 'Заявление', confirmation: definition?.title ?? 'Заявление', waiting: definition?.title ?? 'Помощь',
    'help-options': definition?.title ?? 'Помощь', 'helper-invite': 'Приглашение', 'helper-busy': 'Приглашение', 'helper-ready': 'Приглашение',
    'helper-pending': 'Приглашение', 'trusted-helpers': 'Мои близкие', 'helping-for': 'Кому я помогаю', 'pairing-invite': 'Добавить близкого',
    consultations: 'История помощи', 'consultation-detail': 'Встреча', replay: 'Встреча', 'operator-queue': 'Очередь обращений', 'assist-ended': 'Итоги встречи',
  };
  const hideShellHeader = mode === 'home' || mode === 'helper-active' || mode === 'submitted' || mode === 'assist-busy';
  const bottomNav = mode === 'home' ? 'home' : mode === 'consultations' ? 'history' : mode === 'trusted-helpers' || mode === 'helping-for' ? 'helpers' : null;

  return <AppShell onBack={shellBack} title={shellTitle[mode] ?? 'Рядом'} hideHeader={hideShellHeader}>
    <div className={`screen-view screen-view--${mode}`} key={mode}>
    {mode === 'home' && <Home user={user} launchIntent={launchIntent} onOpenService={(service, existingDraft) => void openService(service, existingDraft)} onOpenOperatorQueue={user.staff ? () => setMode('operator-queue') : undefined} onOpenTrustedHelpers={() => setMode('trusted-helpers')} onOpenHelpingFor={() => setMode('helping-for')} onOpenHistory={() => void openHistory()} onOpenActiveAssist={(id) => void openActiveAssist(id)} onOpenCallback={(nextAssist, invite) => { setAssist(nextAssist); setInviteReady(invite.delivery === 'share_required' ? invite : null); setMode('waiting'); }} />}
    {mode === 'trusted-helpers' && <T1TrustedHelpers />}
    {mode === 'helping-for' && <T5HelpingFor onOpen={(id) => { setAssist({ id } as AssistSession); setMode('helper-active'); }} onPairing={(token) => { setInviteToken(token); setMode('pairing-invite'); }} />}
    {mode === 'pairing-invite' && inviteToken && <T4PairingInvite token={inviteToken} onHome={backToHome} />}
    {mode === 'consultations' && <R1Consultations as="owner" onOpen={(id) => { setHistoryId(id); setMode('consultation-detail'); }} />}
    {mode === 'consultation-detail' && historyId && <R2Consultation id={historyId} onReplay={() => setMode('replay')} />}
    {mode === 'replay' && historyId && <R3Replay id={historyId} />}
    {mode === 'operator-queue' && <O1OperatorQueue onClaim={(id) => { setAssist({ id } as AssistSession); setMode('helper-active'); }} />}
    {mode === 'service' && definition && <S2ServiceCard service={definition} draft={draft} onStart={() => void beginService()} />}
    {mode === 'form' && definition && draft && <S3Form definition={definition} initialSession={draft} onSessionChange={setDraft} onConfirmation={(next) => { setDraft(next); setMode('confirmation'); }} assist={assist ? { id: assist.id, status: realtime.snapshot?.session.status === 'active' || assist.status === 'active' ? 'active' : realtime.snapshot?.session.status ?? assist.status, helpers: realtime.snapshot?.session.participants.filter((item) => item.role !== 'owner' && item.status === 'active').length ?? 0, connection: realtime.connection, recording: realtime.snapshot?.session.recording?.status === 'recording', digitalEmployee: Boolean(realtime.snapshot?.session.participants.some((item) => item.role === 'ai_agent')) } : null} onNeedHelp={() => { setConsent(false); setConsentRequired(false); setAssistError(''); setMode('help-options'); }} onOpenWaiting={() => setMode('waiting')} onEndAssist={() => void finishAssist()} onReleaseDigitalEmployee={() => void releaseAgent()} />}
    {mode === 'help-options' && <S4HelpOptions consentRequired={consentRequired} consent={consent} busy={createAssist.isPending} error={assistError} onConsentChange={setConsent} onSendLink={() => void createAndShare()} onCallTrusted={(id) => void callTrusted(id)} onRequestOperator={(topic) => void requestOperator(topic)} onCallDigitalEmployee={() => void callAgent()} onClose={() => setMode('form')} />}
    {mode === 'waiting' && assist && <S5Waiting session={assist} connection={realtime.connection} operatorRequest={realtime.snapshot?.operator_request} onShareAgain={() => void shareAgain()} onContinue={() => setMode('form')} onEnd={() => void finishAssist()} />}
    {mode === 'confirmation' && draft && <S7Confirmation session={draft} onBack={(next) => { setDraft(next); setMode('form'); }} onSubmitted={(next) => { setResult(next); setMode('submitted'); }} />}
    {mode === 'submitted' && result && <S8Submitted result={result} onHome={backToHome} />}
    {mode === 'helper-invite' && inviteToken && <H1Invite token={inviteToken} consentRequired={consentRequired} consent={consent} busy={false} error={assistError} onConsentChange={setConsent} onAccept={() => void acceptInvite()} onBusy={() => setMode('helper-busy')} onHome={backToHome} onOwnerSession={(id) => { void openActiveAssist(id); }} />}
    {mode === 'helper-busy' && inviteToken && <H5Busy token={inviteToken} onReady={(id) => { setInviteToken(id); setMode('helper-ready'); }} onHome={backToHome} />}
    {mode === 'helper-ready' && inviteToken && <H6Ready callbackId={inviteToken} onHome={backToHome} />}
    {mode === 'helper-pending' && <H2Pending error={realtime.error || assistError} rejected={realtime.rejected} connection={realtime.connection} onHome={backToHome} />}
    {mode === 'helper-active' && helperSnapshot && <H3Helper snapshot={helperSnapshot} connection={realtime.connection} onLeave={() => void leaveAssist()} />}
    {mode === 'helper-active' && !helperSnapshot && <Flex direction="column" gap={12}><Typography.Title>Подключаем помощь</Typography.Title>{helperState.isLoading && <Typography.Text>Загружаем текущий шаг…</Typography.Text>}{(helperState.error || realtime.error) && <div className="notice notice--error"><Typography.Text>{helperState.error instanceof Error ? helperState.error.message : realtime.error || 'Не удалось открыть консультацию.'}</Typography.Text><Button size="small" onClick={() => void helperState.refetch()}>Повторить</Button></div>}</Flex>}
    {mode === 'assist-ended' && assist && <S9Ended sessionId={assist.id} owner={Boolean(realtime.snapshot?.session.me.role === 'owner' || draft)} onContinue={continueAfterAssist} onHome={backToHome} onHistory={() => void openHistory()} />}
    {mode === 'assist-busy' && <S10HelperBusy onSave={() => { void finishAssist().finally(backToHome); }} onOther={() => setMode('help-options')} />}
    {realtime.joinRequest && assist && <S6ApproveHelper helper={realtime.joinRequest} busy={approvalBusy} error={assistError} onApprove={() => void approveJoin(true)} onReject={() => void approveJoin(false)} />}
    {inviteReady && <InviteReadyDialog invite={inviteReady} onClose={() => setInviteReady(null)} />}
    {backAction === 'helper' && <ConfirmDialog title="Выйти из помощи?" description="Вы перестанете видеть заявление и участвовать в разговоре." confirmLabel="Выйти" destructive onCancel={() => setBackAction(null)} onConfirm={() => void leaveAssist()} />}
    {backAction === 'owner' && <ConfirmDialog title="Вернуться на главную?" description="Активная помощь не завершится. Её можно будет открыть снова в разделе «Активная помощь»." confirmLabel="Вернуться" onCancel={() => setBackAction(null)} onConfirm={backToHome} />}
    </div>
    {bottomNav && <BottomNav active={bottomNav} onHome={backToHome} onHistory={() => void openHistory()} onHelpers={() => setMode('trusted-helpers')} />}
  </AppShell>;
}
