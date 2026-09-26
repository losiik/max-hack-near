import { useState } from 'react';
import { Avatar, Button, CellList, CellSimple, Flex, IconButton, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AuthUser, ServiceSession, ServiceSummary } from '../api/client';
import { callHelpCallback, deleteServiceSession, dismissHelpCallback, markHelpCallbackReady, type AssistInvite, type AssistSession, type HelpCallback } from '../api/client';
import { callbacksQuery, queryKeys, queryPolicy, removeCachedSession, servicesQuery, sessionsQuery } from '../api/queries';
import { launchIntentLabel, type LaunchIntent } from '../platform/startParam';
import { ScreenIntro, SectionHeading, StatusMark } from '../components/ScreenIntro';
import { ConfirmDialog } from '../components/AppDialog';

interface HomeProps {
  user: AuthUser;
  launchIntent: LaunchIntent;
  onOpenService: (service: ServiceSummary, draft?: ServiceSession) => void;
  onOpenOperatorQueue?: () => void;
  onOpenTrustedHelpers: () => void;
  onOpenHelpingFor: () => void;
  onOpenHistory: () => void;
  onOpenCallback: (assist: AssistSession, invite: AssistInvite) => void;
}

function TrashIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 7h16M9 7V4h6v3m-9 0 1 13h10l1-13M10 11v5m4-5v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function sessionStatus(session: ServiceSession): string {
  if (session.status === 'submitted') return session.application_number ? `Отправлено · ${session.application_number}` : 'Отправлено';
  if (session.status === 'cancelled') return 'Отменено';
  return `Черновик · шаг ${session.current_step.index} из ${session.total_steps}`;
}

export function Home({ user, launchIntent, onOpenService, onOpenOperatorQueue, onOpenTrustedHelpers, onOpenHelpingFor, onOpenHistory, onOpenCallback }: HomeProps) {
  const queryClient = useQueryClient();
  const [deleteCandidate, setDeleteCandidate] = useState<ServiceSession | null>(null);
  const services = useQuery({ queryKey: queryKeys.services(), queryFn: servicesQuery, ...queryPolicy });
  const sessions = useQuery({ queryKey: queryKeys.sessions(), queryFn: sessionsQuery, ...queryPolicy });
  const ownerCallbacks = useQuery({ queryKey: queryKeys.callbacks('owner'), queryFn: callbacksQuery, ...queryPolicy });
  const helperCallbacks = useQuery({ queryKey: queryKeys.callbacks('helper'), queryFn: callbacksQuery, ...queryPolicy });
  const removeSession = useMutation({
    mutationFn: deleteServiceSession,
    onSuccess: (_, sessionId) => {
      removeCachedSession(queryClient, sessionId);
      setDeleteCandidate(null);
    },
  });
  const error = services.error ?? sessions.error ?? removeSession.error;
  const refreshCallbacks = () => void Promise.all([ownerCallbacks.refetch(), helperCallbacks.refetch()]);
  const callCallback = useMutation({ mutationFn: callHelpCallback, onSuccess: (result) => onOpenCallback(result.assist_session, result.invite) });
  const readyCallback = useMutation({ mutationFn: markHelpCallbackReady, onSuccess: refreshCallbacks });
  const dismissCallback = useMutation({ mutationFn: dismissHelpCallback, onSuccess: refreshCallbacks });

  const draftFor = (code: string) => sessions.data?.find((session) => session.service.code === code && session.status === 'draft');

  return (
    <Flex direction="column" gap={12}>
      <Flex align="center" gap={12} className="profile-intro">
        {user.photo_url ? (
          <Avatar.Container size={56} form="squircle">
            <Avatar.Image src={user.photo_url} alt="" />
          </Avatar.Container>
        ) : (
          <div className="avatar-fallback" aria-hidden="true">
            {user.display_name.slice(0, 1)}
          </div>
        )}
        <Flex direction="column" gap={2}>
          <Typography.Label className="eyebrow">Личный кабинет</Typography.Label>
          <Typography.Headline>{user.display_name}</Typography.Headline>
        </Flex>
      </Flex>

      <section className="home-hero">
        <div className="home-hero__glow" aria-hidden="true" />
        <ScreenIntro
          eyebrow="Сервис рядом"
          title="Оформим вместе"
          description="Заполните заявление сами или позовите близкого — он подскажет голосом и покажет, куда нажать."
        />
        <div className="home-hero__signal"><StatusMark tone="positive" /><Typography.Text>Можно начать сейчас</Typography.Text></div>
      </section>

      {user.staff && <Button size="small" stretched variant="secondary" onClick={onOpenOperatorQueue}>Открыть очередь МФЦ</Button>}
      <Button size="small" stretched variant="secondary" onClick={onOpenTrustedHelpers}>Мои близкие</Button>
      <Button size="small" stretched variant="secondary" onClick={onOpenHelpingFor}>Кому я помогаю</Button>
      <Button size="small" stretched variant="secondary" onClick={onOpenHistory}>Мои консультации</Button>

      {ownerCallbacks.data?.map((callback: HelpCallback) => <div className="notice" key={callback.id}><Flex direction="column" gap={8}><Typography.Label>{callback.status === 'ready' ? `${callback.helper.display_name} готов помочь` : `${callback.helper.display_name} сейчас занят`}</Typography.Label><Typography.Text>{callback.service.title}</Typography.Text>{callback.status === 'ready' ? <Button size="small" stretched disabled={callCallback.isPending} onClick={() => callCallback.mutate(callback.id)}>Позвать</Button> : <Typography.Text className="muted-text">Мы сообщим, когда он освободится.</Typography.Text>}<Button size="small" stretched variant="destructive" disabled={dismissCallback.isPending} onClick={() => dismissCallback.mutate(callback.id)}>Убрать ожидание</Button></Flex></div>)}
      {helperCallbacks.data?.filter((callback) => callback.status === 'busy').map((callback: HelpCallback) => <div className="notice" key={callback.id}><Flex direction="column" gap={8}><Typography.Label>Вы обещали помочь {callback.owner.display_name}</Typography.Label><Typography.Text>{callback.service.title}</Typography.Text><Button size="small" stretched disabled={readyCallback.isPending} onClick={() => readyCallback.mutate(callback.id)}>Освободился</Button></Flex></div>)}

      {error && (
        <div className="notice notice--error">
          <Flex direction="column" gap={10}>
            <Typography.Text>{error instanceof Error ? error.message : 'Не удалось загрузить данные'}</Typography.Text>
            <Button onClick={() => void Promise.all([services.refetch(), sessions.refetch()])}>Повторить</Button>
          </Flex>
        </div>
      )}

      <section className="home-section">
        <SectionHeading title="Услуги" />
        <Typography.Label className="service-category">ЖКХ</Typography.Label>
        {(services.isLoading || sessions.isLoading) && <Typography.Text>Загружаем услуги…</Typography.Text>}
        {services.data?.map((service) => {
          const draft = draftFor(service.code);
          return (
            <div className="service-card" key={service.code}>
              <Typography.Label className="service-card__meta">≈ {service.estimated_minutes} минут · {service.steps_count} шагов</Typography.Label>
              <Typography.Headline>{service.title}</Typography.Headline>
              <Typography.Text className="service-card__description">
                {draft ? `Черновик · шаг ${draft.current_step.index} из ${service.steps_count}` : service.short_description}
              </Typography.Text>
              <Button size="small" stretched onClick={() => onOpenService(service, draft)}>
                {draft ? 'Продолжить' : 'Начать'}
              </Button>
            </div>
          );
        })}
      </section>

      {sessions.data && sessions.data.length > 0 && (
        <section className="home-section">
          <SectionHeading title="Мои заявления" />
          <CellList mode="island" filled>
            {sessions.data.map((session) => (
              <CellSimple
                key={session.id}
                title={session.service.title}
                subtitle={sessionStatus(session)}
                after={
                  <IconButton
                    size="small"
                    variant="ghost"
                    className="delete-icon-button"
                    aria-label={`Удалить заявление «${session.service.title}»`}
                    title="Удалить заявление"
                    onClick={() => setDeleteCandidate(session)}
                  >
                    <TrashIcon />
                  </IconButton>
                }
                surface="island"
              />
            ))}
          </CellList>
        </section>
      )}

      {deleteCandidate && <ConfirmDialog title="Удалить заявление?" description={`«${deleteCandidate.service.title}» будет удалено без возможности восстановления.`} confirmLabel="Удалить" destructive pending={removeSession.isPending} onCancel={() => setDeleteCandidate(null)} onConfirm={() => removeSession.mutate(deleteCandidate.id)} />}

      {launchIntent.kind !== 'home' && (
        <div className="launch-note">
          <Flex direction="column" gap={6}>
            <Typography.Text>Откроется следующий экран</Typography.Text>
            <Typography.Title>{launchIntentLabel(launchIntent)}</Typography.Title>
          </Flex>
        </div>
      )}
    </Flex>
  );
}
