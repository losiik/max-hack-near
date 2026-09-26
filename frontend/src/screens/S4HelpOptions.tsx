import { Button, Flex, Switch, Typography } from '@maxhub/max-ui';
import { ScreenIntro } from '../components/ScreenIntro';
import { useQuery } from '@tanstack/react-query';
import { queryKeys, trustedHelpersQuery } from '../api/queries';
import { InlineAction } from '../components/InlineAction';
import { AppIcon, Surface } from '../components/UiPrimitives';

interface S4HelpOptionsProps {
  consentRequired: boolean;
  consent: boolean;
  busy: boolean;
  error?: string;
  onConsentChange: (value: boolean) => void;
  onSendLink: () => void;
  onCallTrusted: (id: string) => void;
  onRequestOperator: (topic: 'dont_understand' | 'form_error' | 'other') => void;
  onCallDigitalEmployee: () => void;
  onClose: () => void;
}

export function S4HelpOptions({ consentRequired, consent, busy, error, onConsentChange, onSendLink, onCallTrusted, onRequestOperator, onCallDigitalEmployee, onClose }: S4HelpOptionsProps) {
  const helpers = useQuery({ queryKey: queryKeys.trustedHelpers(), queryFn: trustedHelpersQuery });
  return (
    <Flex direction="column" gap={12} className="bottom-sheet">
      <div className="bottom-sheet__handle" />
      <ScreenIntro title="Кого позвать на помощь?" />
      {consentRequired && (
        <label className="switch-field recording-consent">
          <span>Разговор с помощником записывается и сохраняется, чтобы к нему можно было вернуться.</span>
          <Switch checked={consent} onChange={(event) => onConsentChange(event.target.checked)} />
        </label>
      )}
      {error && <div className="notice notice--error">{error}</div>}
      <Surface className="help-option">
        <div className="help-option__heading"><span className="ui-tile ui-tile--orange"><AppIcon name="people" /></span><div><h2>Близкий</h2><p>Получит приглашение в MAX</p></div></div>
        {helpers.data && helpers.data.length > 0 && <Flex direction="column" gap={4}>{helpers.data.map((helper) => <InlineAction key={helper.id} title={helper.alias || helper.helper.display_name} description="Доверенный помощник" action="Позвать" variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={() => onCallTrusted(helper.id)} />)}</Flex>}
        <Button size="small" stretched variant="ghost" disabled={busy || (consentRequired && !consent)} onClick={onSendLink}><AppIcon name="link" />{busy ? 'Готовим ссылку…' : 'Отправить ссылку другому человеку'}</Button>
      </Surface>
      <Surface className="help-option">
        <div className="help-option__heading"><span className="ui-tile ui-tile--purple"><AppIcon name="headset" /></span><div><h2>Сотрудник МФЦ</h2><p>Обычно подключается за 2–5 минут</p></div></div>
        <Typography.Text className="muted-text">Специалист подключится к заявлению и увидит только данные, нужные для помощи.</Typography.Text>
        <Flex direction="column" gap={4}>
          <InlineAction title="Не понимаю, что выбрать" action="Позвать" variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={() => onRequestOperator('dont_understand')} />
          <InlineAction title="Ошибка в форме" action="Позвать" variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={() => onRequestOperator('form_error')} />
          <InlineAction title="Другая причина" action="Позвать" variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={() => onRequestOperator('other')} />
        </Flex>
      </Surface>
      <Surface className="help-option help-option--link"><div className="help-option__heading"><span className="ui-tile ui-tile--blue"><AppIcon name="robot" /></span><div><h2>Цифровой сотрудник</h2><p>Ответит голосом сразу и покажет нужное поле</p></div></div><Button size="small" variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={onCallDigitalEmployee}>Позвать</Button></Surface>
      <div className="privacy-note">
        <AppIcon name="shield" /><Typography.Text>
          Помощник увидит текущий шаг, услышит вас и сможет показать, куда нажать. Он не увидит СНИЛС, номер счёта и коды из SMS.
        </Typography.Text>
      </div>
      <Button size="small" variant="ghost" onClick={onClose}>Вернуться к заявлению</Button>
    </Flex>
  );
}
