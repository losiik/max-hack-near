import { Button } from '@maxhub/max-ui';
import type { ServiceDefinition, ServiceSession } from '../api/client';
import { ScreenIntro } from '../components/ScreenIntro';
import { AppIcon, Surface } from '../components/UiPrimitives';

interface S2ServiceCardProps {
  service: ServiceDefinition;
  draft?: ServiceSession;
  onStart: () => void;
}

export function S2ServiceCard({ service, draft, onStart }: S2ServiceCardProps) {
  return (
    <div className="ui-page service-card-screen">
      <ScreenIntro eyebrow="Социальная поддержка" title={service.title} />
      <div className="ui-chips"><span><AppIcon name="clock" />≈ {service.estimated_minutes} минут</span><span>{service.steps.length} шагов</span><span>Онлайн</span></div>
      <p className="ui-lead">{service.short_description}</p>
      <Surface><h2>Кому положена</h2><ul className="ui-bullets"><li>Пенсионерам по старости</li><li>Ветеранам труда</li><li>Людям с инвалидностью и семьям с ребёнком-инвалидом</li><li>Многодетным и малоимущим семьям</li></ul></Surface>
      <Surface><h2>Что понадобится</h2><ul className="ui-check-list"><li><AppIcon name="document" />СНИЛС</li><li><AppIcon name="document" />Документ, подтверждающий льготу</li><li><AppIcon name="document" />Сведения о доходе семьи</li><li><AppIcon name="document" />Номер счёта или индекс почтового отделения</li></ul></Surface>
      <Surface tone="blue" className="service-help-card"><AppIcon name="people" /><div><h2>Можно заполнить вместе</h2><p>Близкий, сотрудник МФЦ или цифровой сотрудник подскажут голосом и покажут, куда нажать. Личные данные они не увидят.</p></div></Surface>
      {draft && <Surface tone="green"><strong>Ваш черновик</strong><p>Сохранён на шаге «{draft.current_step.title}»</p></Surface>}
      {service.disclaimer && <p className="ui-caption">{service.disclaimer}</p>}
      <div className="screen-cta"><Button size="small" stretched onClick={onStart}>{draft ? 'Продолжить оформление' : 'Начать заполнение'}</Button></div>
    </div>
  );
}
