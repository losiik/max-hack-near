import { Button, Flex, Switch, Typography } from '@maxhub/max-ui';
import { ScreenIntro } from '../components/ScreenIntro';
import { useQuery } from '@tanstack/react-query';
import { queryKeys, trustedHelpersQuery } from '../api/queries';

interface S4HelpOptionsProps {
  consentRequired: boolean;
  consent: boolean;
  busy: boolean;
  error?: string;
  onConsentChange: (value: boolean) => void;
  onSendLink: () => void;
  onCallTrusted: (id: string) => void;
  onRequestOperator: (topic: 'dont_understand' | 'form_error' | 'other') => void;
  onClose: () => void;
}

export function S4HelpOptions({ consentRequired, consent, busy, error, onConsentChange, onSendLink, onCallTrusted, onRequestOperator, onClose }: S4HelpOptionsProps) {
  const helpers = useQuery({ queryKey: queryKeys.trustedHelpers(), queryFn: trustedHelpersQuery });
  return (
    <Flex direction="column" gap={12} className="bottom-sheet">
      <ScreenIntro eyebrow="Помощь рядом" title="Позвать близкого" description="Отправьте ссылку человеку, которому доверяете." />
      {consentRequired && (
        <label className="switch-field">
          <span>Разговор с помощником записывается и сохраняется, чтобы к нему можно было вернуться.</span>
          <Switch checked={consent} onChange={(event) => onConsentChange(event.target.checked)} />
        </label>
      )}
      {error && <div className="notice notice--error">{error}</div>}
      <Button variant="primary" size="small" stretched disabled={busy || (consentRequired && !consent)} onClick={onSendLink}>
        {busy ? 'Готовим ссылку…' : 'Подготовить ссылку'}
      </Button>
      {helpers.data && helpers.data.length > 0 && <section className="help-option"><Typography.Label>Мои близкие</Typography.Label><Flex direction="column" gap={8}>{helpers.data.map((helper) => <Button key={helper.id} size="small" stretched variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={() => onCallTrusted(helper.id)}>Позвать {helper.alias || helper.helper.display_name}</Button>)}</Flex></section>}
      <section className="help-option">
        <Typography.Label>Специалист МФЦ</Typography.Label>
        <Typography.Text className="muted-text">Специалист подключится к заявлению и увидит только данные, нужные для помощи.</Typography.Text>
        <Flex direction="column" gap={8}>
          <Button size="small" stretched variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={() => onRequestOperator('dont_understand')}>Не понимаю, что выбрать</Button>
          <Button size="small" stretched variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={() => onRequestOperator('form_error')}>Ошибка в форме</Button>
          <Button size="small" stretched variant="secondary" disabled={busy || (consentRequired && !consent)} onClick={() => onRequestOperator('other')}>Другая причина</Button>
        </Flex>
      </section>
      <div className="privacy-note">
        <Typography.Text>
          Помощник увидит текущий шаг, услышит вас и сможет показать, куда нажать. Он не увидит СНИЛС, номер счёта и коды из SMS.
        </Typography.Text>
      </div>
      <Button variant="ghost" onClick={onClose}>Вернуться к заявлению</Button>
    </Flex>
  );
}
