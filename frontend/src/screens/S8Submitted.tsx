import { Button } from '@maxhub/max-ui';
import type { SubmitResult } from '../api/client';
import { StatusScreen, Surface } from '../components/UiPrimitives';

export function S8Submitted({ result, onHome }: { result: SubmitResult; onHome: () => void }) {
  return (
    <div className="ui-page submitted-screen">
      <StatusScreen icon="check" tone="green" title="Заявление отправлено"><div className="submitted-number">№ {result.application_number}</div></StatusScreen>
      <Surface><h2>Что дальше</h2><ol className="ui-numbered-list"><li>Заявление рассмотрят в течение 10 рабочих дней</li><li>Решение придёт сообщением в MAX</li><li>Если понадобятся документы, с вами свяжутся</li></ol></Surface>
      <p className="ui-caption ui-caption--center">Это демонстрационная услуга: заявление никуда не отправлено.</p>
      <div className="screen-actions"><Button size="small" stretched onClick={onHome}>На главную</Button></div>
    </div>
  );
}
