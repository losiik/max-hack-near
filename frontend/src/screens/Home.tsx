import { useState } from 'react';
import { Avatar, Button, CellList, CellSimple, Flex, IconButton, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AuthUser, ServiceSession, ServiceSummary } from '../api/client';
import { deleteServiceSession } from '../api/client';
import { queryKeys, queryPolicy, removeCachedSession, servicesQuery, sessionsQuery } from '../api/queries';
import { launchIntentLabel, type LaunchIntent } from '../platform/startParam';
import { ScreenIntro, SectionHeading, StatusMark } from '../components/ScreenIntro';

interface HomeProps {
  user: AuthUser;
  launchIntent: LaunchIntent;
  onOpenService: (service: ServiceSummary, draft?: ServiceSession) => void;
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

export function Home({ user, launchIntent, onOpenService }: HomeProps) {
  const queryClient = useQueryClient();
  const [deleteCandidate, setDeleteCandidate] = useState<ServiceSession | null>(null);
  const services = useQuery({ queryKey: queryKeys.services(), queryFn: servicesQuery, ...queryPolicy });
  const sessions = useQuery({ queryKey: queryKeys.sessions(), queryFn: sessionsQuery, ...queryPolicy });
  const removeSession = useMutation({
    mutationFn: deleteServiceSession,
    onSuccess: (_, sessionId) => {
      removeCachedSession(queryClient, sessionId);
      setDeleteCandidate(null);
    },
  });
  const error = services.error ?? sessions.error ?? removeSession.error;

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

      {deleteCandidate && (
        <div className="delete-confirm" role="alertdialog" aria-labelledby="delete-application-title">
          <Typography.Title id="delete-application-title">Удалить заявление?</Typography.Title>
          <Typography.Text>«{deleteCandidate.service.title}» будет удалено без возможности восстановления.</Typography.Text>
          <Flex gap={8} className="delete-confirm__actions">
            <Button size="small" stretched variant="secondary" disabled={removeSession.isPending} onClick={() => setDeleteCandidate(null)}>Отмена</Button>
            <Button size="small" stretched variant="destructive" loading={removeSession.isPending} onClick={() => removeSession.mutate(deleteCandidate.id)}>Удалить</Button>
          </Flex>
        </div>
      )}

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
