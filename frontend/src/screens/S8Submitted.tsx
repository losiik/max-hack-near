import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { SubmitResult } from '../api/client';
import { ScreenIntro } from '../components/ScreenIntro';

export function S8Submitted({ result, onHome }: { result: SubmitResult; onHome: () => void }) {
  return (
    <Flex direction="column" gap={12} className="submitted-screen">
      <ScreenIntro eyebrow="Готово" title="Заявление отправлено" description="Мы сохранили результат демо-оформления." />
      <div className="submitted-number"><Typography.Label>Номер заявления</Typography.Label><Typography.Headline>{result.application_number}</Typography.Headline></div>
      <Typography.Text>
        Это демо-услуга: заявление никуда не направляется, а данные не передаются в государственные системы.
      </Typography.Text>
      <Button size="small" stretched onClick={onHome}>На главную</Button>
    </Flex>
  );
}
