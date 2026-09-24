import { Button, CellList, CellSimple, Flex, Typography } from '@maxhub/max-ui';
import type { ServiceDefinition, ServiceSession } from '../api/client';
import { ScreenIntro, SectionHeading } from '../components/ScreenIntro';

interface S2ServiceCardProps {
  service: ServiceDefinition;
  draft?: ServiceSession;
  onStart: () => void;
}

export function S2ServiceCard({ service, draft, onStart }: S2ServiceCardProps) {
  return (
    <Flex direction="column" gap={12}>
      <ScreenIntro eyebrow="Услуга" title={service.title} description={service.short_description} meta={`≈ ${service.estimated_minutes} минут · ${service.steps.length} шагов`} />

      <section className="detail-section">
        <SectionHeading title="Что понадобится" />
        <CellList mode="island" filled>
          <CellSimple title="СНИЛС" subtitle="Нужен для проверки права на компенсацию" before={<span className="requirement-icon">01</span>} surface="island" />
          <CellSimple title="Реквизиты" subtitle="Номер счёта для выплаты" before={<span className="requirement-icon">02</span>} surface="island" />
        </CellList>
      </section>

      {service.disclaimer && <div className="notice notice--subtle"><Typography.Text>{service.disclaimer}</Typography.Text></div>}

      {draft && <div className="draft-note"><Typography.Label>Ваш черновик</Typography.Label><Typography.Text>Сохранён на шаге «{draft.current_step.title}»</Typography.Text></div>}
      <div className="screen-cta"><Button size="small" stretched onClick={onStart}>{draft ? 'Продолжить оформление' : 'Начать оформление'}</Button></div>
    </Flex>
  );
}
