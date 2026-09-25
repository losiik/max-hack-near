import { Button, Flex, Switch, Typography } from '@maxhub/max-ui';
import { ScreenIntro } from '../components/ScreenIntro';

interface S4HelpOptionsProps {
  consentRequired: boolean;
  consent: boolean;
  busy: boolean;
  error?: string;
  onConsentChange: (value: boolean) => void;
  onSendLink: () => void;
  onClose: () => void;
}

export function S4HelpOptions({ consentRequired, consent, busy, error, onConsentChange, onSendLink, onClose }: S4HelpOptionsProps) {
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
      <div className="privacy-note">
        <Typography.Text>
          Помощник увидит текущий шаг, услышит вас и сможет показать, куда нажать. Он не увидит СНИЛС, номер счёта и коды из SMS.
        </Typography.Text>
      </div>
      <Button variant="ghost" onClick={onClose}>Вернуться к заявлению</Button>
    </Flex>
  );
}
