import { useEffect, useMemo, useState } from 'react';
import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { acceptAssistInvite, agreeToRecording, ApiError, approveAssistParticipant, createAssistInvite, createAssistSession, endAssistSession, leaveAssistSession, loginWithMax, rejectAssistParticipant, requestOperatorForApplication, startServiceSession, type AssistInvite, type AssistSession, type AuthUser, type ServiceDefinition, type ServiceSession, type ServiceSummary, type SubmitResult } from './api/client';
import { InviteReadyDialog } from './components/InviteReadyDialog';
import { cacheAssistSession, cacheSession, queryKeys, serviceQuery } from './api/queries';
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
import { getDisplayNameHint, getInitData, getStartParam, isMaxRuntime } from './platform/maxBridge';
import { parseStartParam, type LaunchIntent } from './platform/startParam';
import { useAssistStore } from './realtime/assistStore';
import { useAssistSocket } from './realtime/useAssistSocket';

type AppMode = 'loading' | 'dev' | 'home' | 'operator-queue' | 'trusted-helpers' | 'pairing-invite' | 'service' | 'form' | 'confirmation' | 'submitted' | 'help-options' | 'waiting' | 'helper-invite' | 'helper-pending' | 'helper-active' | 'assist-ended' | 'error';

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
  const [consent, setConsent] = useState(false);
  const [inviteReady, setInviteReady] = useState<AssistInvite | null>(null);
  const [consentRequired, setConsentRequired] = useState(false);
  const [assistError, setAssistError] = useState('');
  const maxUserHint = useMemo(getDisplayNameHint, []);
  const realtime = useAssistStore();
  useAssistSocket(assist?.id ?? null);
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
    loginWithMax(getInitData()).then((response) => {
      beginUserSession(response.user);
      if (intent.kind === 'assist_invite') { setInviteToken(intent.token); setMode('helper-invite'); } else if (intent.kind === 'pairing') { setInviteToken(intent.token); setMode('pairing-invite'); } else setMode('home');
    }).catch((reason: Error) => { setError(reason.message); setMode('error'); });
  }, []);

  useEffect(() => {
    if (mode === 'helper-pending' && realtime.snapshot) setMode('helper-active');
    if (realtime.endedReason && assist && mode !== 'assist-ended') setMode('assist-ended');
  }, [assist, mode, realtime.endedReason, realtime.snapshot]);

  if (mode === 'loading') return <AppShell><A0 message={maxUserHint ? `Входим как ${maxUserHint}` : undefined} /></AppShell>;
  if (mode === 'dev') return <AppShell><D1 onLogin={(nextUser) => { beginUserSession(nextUser); setMode('home'); }} /></AppShell>;
  if (mode === 'error') return <AppShell><Flex direction="column" gap={12}><Typography.Title>Не удалось продолжить</Typography.Title><Typography.Text>{error || 'Откройте приложение из MAX и попробуйте снова.'}</Typography.Text><Button onClick={() => window.location.reload()}>Повторить</Button></Flex></AppShell>;

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
      const nextAssist = await createAssist.mutateAsync(draft.id);
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
  async function finishAssist() {
    if (!assist) return;
    try { await endAssistSession(assist.id); setMode('assist-ended'); }
    catch (reason) { setAssistError(reason instanceof Error ? reason.message : 'Не удалось завершить помощь.'); }
  }
  async function approveJoin(approved: boolean) {
    if (!assist || !realtime.joinRequest) return;
    setAssistError('');
    try {
      const next = approved ? await approveAssistParticipant(assist.id, realtime.joinRequest.id) : await rejectAssistParticipant(assist.id, realtime.joinRequest.id);
      cacheAssistSession(queryClient, next); setAssist(next); useAssistStore.getState().clearJoinRequest();
    } catch (reason) { setAssistError(reason instanceof Error ? reason.message : 'Не удалось обновить подключение.'); }
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
    try { await leaveAssistSession(assist.id); useAssistStore.getState().reset(); setAssist(null); setMode('home'); }
    catch (reason) { setAssistError(reason instanceof Error ? reason.message : 'Не удалось выйти из помощи.'); }
  }
  const backToHome = () => { useAssistStore.getState().reset(); setAssist(null); setMode('home'); };
  const shellBack = mode === 'home' ? undefined : backToHome;
  if (!user) return null;

  return <AppShell onBack={shellBack}>
    {mode === 'home' && <Home user={user} launchIntent={launchIntent} onOpenService={(service, existingDraft) => void openService(service, existingDraft)} onOpenOperatorQueue={user.staff ? () => setMode('operator-queue') : undefined} onOpenTrustedHelpers={() => setMode('trusted-helpers')} />}
    {mode === 'trusted-helpers' && <T1TrustedHelpers />}
    {mode === 'pairing-invite' && inviteToken && <T4PairingInvite token={inviteToken} onHome={backToHome} />}
    {mode === 'operator-queue' && <O1OperatorQueue onClaim={(id) => { setAssist({ id } as AssistSession); setMode('helper-active'); }} />}
    {mode === 'service' && definition && <S2ServiceCard service={definition} draft={draft} onStart={() => void beginService()} />}
    {mode === 'form' && definition && draft && <S3Form definition={definition} initialSession={draft} onSessionChange={setDraft} onConfirmation={(next) => { setDraft(next); setMode('confirmation'); }} assist={assist ? { status: realtime.snapshot?.session.status ?? assist.status, helpers: realtime.snapshot?.session.participants.filter((item) => item.role !== 'owner').length ?? 0, connection: realtime.connection } : null} onNeedHelp={() => { setConsent(false); setConsentRequired(false); setAssistError(''); setMode('help-options'); }} onOpenWaiting={() => setMode('waiting')} />}
    {mode === 'help-options' && <S4HelpOptions consentRequired={consentRequired} consent={consent} busy={createAssist.isPending} error={assistError} onConsentChange={setConsent} onSendLink={() => void createAndShare()} onCallTrusted={(id) => void callTrusted(id)} onRequestOperator={(topic) => void requestOperator(topic)} onClose={() => setMode('form')} />}
    {mode === 'waiting' && assist && <S5Waiting session={assist} connection={realtime.connection} operatorRequest={realtime.snapshot?.operator_request} onShareAgain={() => void shareAgain()} onContinue={() => setMode('form')} onEnd={() => void finishAssist()} />}
    {mode === 'confirmation' && draft && <S7Confirmation session={draft} onBack={(next) => { setDraft(next); setMode('form'); }} onSubmitted={(next) => { setResult(next); setMode('submitted'); }} />}
    {mode === 'submitted' && result && <S8Submitted result={result} onHome={backToHome} />}
    {mode === 'helper-invite' && inviteToken && <H1Invite token={inviteToken} consentRequired={consentRequired} consent={consent} busy={false} error={assistError} onConsentChange={setConsent} onAccept={() => void acceptInvite()} onHome={backToHome} onOwnerSession={(id) => { setAssist({ id } as AssistSession); setMode('waiting'); }} />}
    {mode === 'helper-pending' && <H2Pending error={realtime.error || assistError} onHome={backToHome} />}
    {mode === 'helper-active' && realtime.snapshot && <H3Helper snapshot={realtime.snapshot} connection={realtime.connection} onLeave={() => void leaveAssist()} />}
    {mode === 'assist-ended' && assist && <S9Ended sessionId={assist.id} owner={Boolean(realtime.snapshot?.session.me.role === 'owner' || draft)} onContinue={() => setMode('form')} onHome={backToHome} />}
    {realtime.joinRequest && assist && <S6ApproveHelper helper={realtime.joinRequest} busy={false} error={assistError} onApprove={() => void approveJoin(true)} onReject={() => void approveJoin(false)} />}
    {inviteReady && <InviteReadyDialog invite={inviteReady} onClose={() => setInviteReady(null)} />}
  </AppShell>;
}
