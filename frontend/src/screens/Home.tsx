import { useState } from "react";
import { Button, Flex, Typography } from "@maxhub/max-ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  ActiveAssist,
  AuthUser,
  ServiceSession,
  ServiceSummary,
} from "../api/client";
import {
  callHelpCallback,
  deleteServiceSession,
  dismissHelpCallback,
  markHelpCallbackReady,
  type AssistInvite,
  type AssistSession,
  type HelpCallback,
} from "../api/client";
import {
  activeAssistsQuery,
  callbacksQuery,
  queryKeys,
  queryPolicy,
  removeCachedSession,
  servicesQuery,
  sessionsQuery,
} from "../api/queries";
import { launchIntentLabel, type LaunchIntent } from "../platform/startParam";
import { SectionHeading, StatusMark } from "../components/ScreenIntro";
import { ConfirmDialog } from "../components/AppDialog";
import {
  AppIcon,
  IconButton,
  ListRow,
  PersonRow,
  Surface,
} from "../components/UiPrimitives";

interface HomeProps {
  user: AuthUser;
  launchIntent: LaunchIntent;
  onOpenServices: () => void;
  onOpenService: (service: ServiceSummary, draft?: ServiceSession) => void;
  onOpenOperatorQueue?: () => void;
  onOpenTrustedHelpers: () => void;
  onOpenHelpingFor: () => void;
  onOpenHistory: () => void;
  onOpenCallback: (assist: AssistSession, invite: AssistInvite) => void;
  onOpenActiveAssist: (id: string) => void;
}

function sessionStatus(session: ServiceSession): string {
  if (session.status === "submitted")
    return session.application_number
      ? `Отправлено · ${session.application_number}`
      : "Отправлено";
  if (session.status === "cancelled") return "Отменено";
  return `Черновик · шаг ${session.current_step.index} из ${session.total_steps}`;
}

export function Home({
  user,
  launchIntent,
  onOpenServices,
  onOpenService,
  onOpenOperatorQueue,
  onOpenTrustedHelpers,
  onOpenHelpingFor,
  onOpenHistory,
  onOpenCallback,
  onOpenActiveAssist,
}: HomeProps) {
  const queryClient = useQueryClient();
  const [deleteCandidate, setDeleteCandidate] = useState<ServiceSession | null>(
    null,
  );
  const services = useQuery({
    queryKey: queryKeys.services(),
    queryFn: servicesQuery,
    ...queryPolicy,
  });
  const sessions = useQuery({
    queryKey: queryKeys.sessions(),
    queryFn: sessionsQuery,
    ...queryPolicy,
  });
  const ownerCallbacks = useQuery({
    queryKey: queryKeys.callbacks("owner"),
    queryFn: callbacksQuery,
    ...queryPolicy,
  });
  const helperCallbacks = useQuery({
    queryKey: queryKeys.callbacks("helper"),
    queryFn: callbacksQuery,
    ...queryPolicy,
  });
  const activeAssists = useQuery({
    queryKey: queryKeys.activeAssists(),
    queryFn: activeAssistsQuery,
    ...queryPolicy,
  });
  const removeSession = useMutation({
    mutationFn: deleteServiceSession,
    onSuccess: (_, sessionId) => {
      removeCachedSession(queryClient, sessionId);
      setDeleteCandidate(null);
    },
  });
  const error = services.error ?? sessions.error ?? removeSession.error;
  const refreshCallbacks = () =>
    void Promise.all([ownerCallbacks.refetch(), helperCallbacks.refetch()]);
  const callCallback = useMutation({
    mutationFn: callHelpCallback,
    onSuccess: (result) => onOpenCallback(result.assist_session, result.invite),
  });
  const readyCallback = useMutation({
    mutationFn: markHelpCallbackReady,
    onSuccess: refreshCallbacks,
  });
  const dismissCallback = useMutation({
    mutationFn: dismissHelpCallback,
    onSuccess: refreshCallbacks,
  });

  const draftFor = (code: string) =>
    sessions.data?.find(
      (session) => session.service.code === code && session.status === "draft",
    );
  const firstService = services.data?.[0];
  const firstDraft = firstService ? draftFor(firstService.code) : undefined;

  return (
    <div className="ui-page home-page">
      <header className="home-heading">
        <div>
          <div className="home-heading__brand">Рядом</div>
          <div className="home-heading__subtitle">
            Заполнить заявление проще и спокойнее
          </div>
        </div>
        <PersonRow
          name={user.display_name}
          photoUrl={user.photo_url}
          initials={user.display_name.slice(0, 1)}
          tone="blue"
        />
      </header>
      <section className="home-hero">
        <div className="home-hero__copy">
          <h1>
            {firstDraft ? "Продолжить заявление" : "Начать новое заявление"}
          </h1>
          <p>
            Пошагово проведём по форме, а если что-то непонятно — можно позвать
            помощь.
          </p>
          <Button
            size="small"
            onClick={() => firstDraft && firstService ? onOpenService(firstService, firstDraft) : onOpenServices()}
          >
            {firstDraft ? "Продолжить" : "Начать"}
            <AppIcon name="arrow-right" />
          </Button>
        </div>
        <div className="home-hero__art" aria-hidden="true">
          <AppIcon name="document" />
          <i />
        </div>
      </section>

      {activeAssists.error && (
        <div className="notice notice--error" role="alert">
          <Flex direction="column" gap={8}>
            <Typography.Text>
              {activeAssists.error instanceof Error
                ? activeAssists.error.message
                : "Не удалось загрузить активную помощь."}
            </Typography.Text>
            <Button size="small" onClick={() => void activeAssists.refetch()}>
              Повторить
            </Button>
          </Flex>
        </div>
      )}
      {activeAssists.data && activeAssists.data.length > 0 && (
        <section className="home-section">
          <SectionHeading title="Активная помощь" />
          {activeAssists.data.map((item: ActiveAssist) => (
            <Surface key={item.id} tone="green" className="active-assist-card">
              <div className="active-assist-card__title">
                <StatusMark tone="positive" />
                {item.my_role === "owner"
                  ? "Вам помогают"
                  : `Вы помогаете ${item.owner_display_name}`}
              </div>
              <PersonRow
                name={item.service_title}
                meta={`Шаг ${item.current_step.index} из ${item.total_steps} · ${item.status === "active" ? "идёт сейчас" : "ждём подключения"}`}
                tone="green"
                online={item.status === "active"}
              />
              <Button
                size="small"
                stretched
                variant="secondary"
                onClick={() => onOpenActiveAssist(item.id)}
              >
                Вернуться к заявлению
              </Button>
            </Surface>
          ))}
        </section>
      )}

      {ownerCallbacks.data?.map((callback: HelpCallback) => (
        <Surface tone="warning" key={callback.id} className="callback-card">
          <PersonRow
            name={
              callback.status === "ready"
                ? `${callback.helper.display_name} готов помочь`
                : `${callback.helper.display_name} сейчас занят`
            }
            meta={callback.service.title}
            tone="orange"
          />
          <div className="callback-card__actions">
            {callback.status === "ready" ? (
              <Button
                size="small"
                disabled={callCallback.isPending}
                onClick={() => callCallback.mutate(callback.id)}
              >
                Позвать
              </Button>
            ) : (
              <span>Сообщим, когда он освободится.</span>
            )}
            <Button
              size="small"
              variant="destructive"
              disabled={dismissCallback.isPending}
              onClick={() => dismissCallback.mutate(callback.id)}
            >
              Убрать ожидание
            </Button>
          </div>
        </Surface>
      ))}
      {helperCallbacks.data
        ?.filter((callback) => callback.status === "busy")
        .map((callback: HelpCallback) => (
          <Surface tone="warning" key={callback.id} className="callback-card">
            <PersonRow
              name={`Вы обещали помочь ${callback.owner.display_name}`}
              meta={callback.service.title}
              tone="orange"
            />
            <Button
              size="small"
              stretched
              disabled={readyCallback.isPending}
              onClick={() => readyCallback.mutate(callback.id)}
            >
              Я освободился
            </Button>
          </Surface>
        ))}

      {error && (
        <div className="notice notice--error">
          <Flex direction="column" gap={10}>
            <Typography.Text>
              {error instanceof Error
                ? error.message
                : "Не удалось загрузить данные"}
            </Typography.Text>
            <Button
              onClick={() =>
                void Promise.all([services.refetch(), sessions.refetch()])
              }
            >
              Повторить
            </Button>
          </Flex>
        </div>
      )}

      {(services.isLoading || sessions.isLoading) && (
        <Typography.Text>Загружаем услуги…</Typography.Text>
      )}
      {sessions.data?.some((item) => item.status === "draft") && (
        <section className="home-section">
          <SectionHeading title="Продолжить оформление" />
          <div className="ui-list">
            {sessions.data
              .filter((item) => item.status === "draft")
              .map((session) => (
                <ListRow
                  key={session.id}
                  icon="document"
                  title={session.service.title}
                  subtitle={`Шаг ${session.current_step.index} из ${session.total_steps} · сохранено автоматически`}
                  onClick={() => {
                    const service = services.data?.find(
                      (item) => item.code === session.service.code,
                    );
                    if (service) onOpenService(service, session);
                  }}
                />
              ))}
          </div>
        </section>
      )}

      <section className="home-section">
        <SectionHeading title="Быстрые действия" />
        <div className="ui-list">
          <ListRow
            icon="people"
            iconTone="orange"
            title="Мои близкие"
            subtitle="Кого можно позвать одним нажатием"
            onClick={onOpenTrustedHelpers}
          />
          <ListRow
            icon="shield"
            iconTone="blue"
            title="Кому я помогаю"
            subtitle="Люди, которые доверили вам помощь"
            onClick={onOpenHelpingFor}
          />
          <ListRow
            icon="history"
            iconTone="green"
            title="История помощи"
            subtitle=""
            onClick={onOpenHistory}
          />
          {user.staff && onOpenOperatorQueue && (
            <ListRow
              icon="headset"
              iconTone="purple"
              title="Очередь обращений"
              subtitle="Рабочее место сотрудника МФЦ"
              onClick={onOpenOperatorQueue}
            />
          )}
        </div>
      </section>

      {sessions.data && sessions.data.length > 0 && (
        <section className="home-section applications-section">
          <SectionHeading title="Мои заявления" />
          <div className="ui-list">
            {sessions.data.map((session) => (
              <ListRow
                key={session.id}
                icon="document"
                title={session.service.title}
                subtitle={sessionStatus(session)}
                trailing={
                  <IconButton
                    tone="danger"
                    icon="trash"
                    label={`Удалить заявление «${session.service.title}»`}
                    onClick={() => setDeleteCandidate(session)}
                  />
                }
              />
            ))}
          </div>
        </section>
      )}

      <Surface className="how-it-works">
        <SectionHeading title="Как это работает" />
        <ol>
          <li>
            <span className="ui-tile ui-tile--blue">
              <AppIcon name="document" />
            </span>
            <span>Выберите услугу</span>
          </li>
          <li>
            <span className="ui-tile ui-tile--purple">
              <AppIcon name="people" />
            </span>
            <span>Заполните вместе</span>
          </li>
          <li>
            <span className="ui-tile ui-tile--green">
              <AppIcon name="check" />
            </span>
            <span>Отправьте заявление</span>
          </li>
        </ol>
      </Surface>

      {deleteCandidate && (
        <ConfirmDialog
          title="Удалить заявление?"
          description={`«${deleteCandidate.service.title}» будет удалено без возможности восстановления.`}
          confirmLabel="Удалить"
          destructive
          pending={removeSession.isPending}
          onCancel={() => setDeleteCandidate(null)}
          onConfirm={() => removeSession.mutate(deleteCandidate.id)}
        />
      )}

      {launchIntent.kind !== "home" && (
        <div className="launch-note">
          <Flex direction="column" gap={6}>
            <Typography.Text>Откроется следующий экран</Typography.Text>
            <Typography.Title>
              {launchIntentLabel(launchIntent)}
            </Typography.Title>
          </Flex>
        </div>
      )}
    </div>
  );
}
