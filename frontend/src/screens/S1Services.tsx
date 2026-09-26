import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import type { ServiceSession, ServiceSummary } from '../api/client';
import { queryKeys, queryPolicy, servicesQuery, sessionsQuery } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';
import { ListRow } from '../components/UiPrimitives';

interface S1ServicesProps {
  onOpenService: (service: ServiceSummary, draft?: ServiceSession) => void;
}

export function S1Services({ onOpenService }: S1ServicesProps) {
  const services = useQuery({ queryKey: queryKeys.services(), queryFn: servicesQuery, ...queryPolicy });
  const sessions = useQuery({ queryKey: queryKeys.sessions(), queryFn: sessionsQuery, ...queryPolicy });

  const draftFor = (code: string) => sessions.data?.find((session) => session.service.code === code && session.status === 'draft');

  return <div className="ui-page services-screen">
    <ScreenIntro title="Услуги" description="Выберите услугу — мы проведём по заявлению шаг за шагом." />
    {(services.isLoading || sessions.isLoading) && <Typography.Text>Загружаем услуги…</Typography.Text>}
    {(services.error || sessions.error) && <div className="notice notice--error" role="alert">
      <Flex direction="column" gap={8}>
        <Typography.Text>{services.error instanceof Error ? services.error.message : sessions.error instanceof Error ? sessions.error.message : 'Не удалось загрузить услуги.'}</Typography.Text>
        <Button size="small" onClick={() => void Promise.all([services.refetch(), sessions.refetch()])}>Повторить</Button>
      </Flex>
    </div>}
    {services.data && services.data.length === 0 && <Typography.Text className="muted-text">Доступных услуг пока нет.</Typography.Text>}
    {services.data && services.data.length > 0 && <div className="ui-list services-list">
      {services.data.map((service) => {
        const draft = draftFor(service.code);
        return <ListRow
          key={service.code}
          icon="document"
          title={service.title}
          subtitle={draft ? `Черновик · шаг ${draft.current_step.index} из ${service.steps_count}` : `≈ ${service.estimated_minutes} минут · ${service.steps_count} шагов`}
          onClick={() => onOpenService(service, draft)}
        />;
      })}
    </div>}
  </div>;
}
