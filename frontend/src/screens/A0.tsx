import { Flex, Typography } from '@maxhub/max-ui';

export function A0({ message = 'Подключаем приложение' }: { message?: string }) {
  return (
    <Flex direction="column" align="center" gap={12} className="screen-center">
      <span className="loading-mark" aria-hidden="true" />
      <Typography.Title>Рядом</Typography.Title>
      <Typography.Text>{message}</Typography.Text>
    </Flex>
  );
}
