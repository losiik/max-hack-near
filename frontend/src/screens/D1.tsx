import { useState } from 'react';
import { Button, Flex, Panel, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery } from '@tanstack/react-query';
import { loginWithDev, type AuthUser, type DevUser } from '../api/client';
import { devUsersQuery, queryKeys } from '../api/queries';
import { launchIntentLabel, parseStartParam } from '../platform/startParam';

interface D1Props {
  onLogin: (user: AuthUser) => void;
}

export function D1({ onLogin }: D1Props) {
  const [startParam, setStartParam] = useState('');
  const [preview, setPreview] = useState('');
  const [error, setError] = useState('');
  const users = useQuery({ queryKey: queryKeys.devUsers(), queryFn: devUsersQuery });
  const login = useMutation({ mutationFn: loginWithDev });

  async function chooseUser(user: DevUser) {
    setError('');
    try {
      const response = await login.mutateAsync(user.user_key);
      onLogin(response.user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось войти');
    }
  }

  return (
    <Flex direction="column" gap={20}>
      <div>
        <Typography.Title>Режим разработки</Typography.Title>
        <Typography.Text>Выберите пользователя, чтобы проверить сценарий без MAX.</Typography.Text>
      </div>

      {(error || users.error) && <Panel className="notice notice--error">{error || (users.error as Error).message}</Panel>}

      <Flex direction="column" gap={10}>
        <Typography.Text>Пользователь</Typography.Text>
        {users.isLoading && <Typography.Text>Загружаем список…</Typography.Text>}
        {users.data?.map((user) => (
          <Button
            key={user.user_key}
            disabled={login.isPending}
            onClick={() => void chooseUser(user)}
            className="choice-button"
          >
            <span>{user.display_name}</span>
            <small>{user.role_hint}</small>
          </Button>
        ))}
      </Flex>

      <Flex direction="column" gap={10}>
        <Typography.Text>Проверить deep link</Typography.Text>
        <input
          className="max-input"
          value={startParam}
          onChange={(event) => setStartParam(event.target.value)}
          placeholder="as_Ab12Cd34"
          aria-label="Параметр запуска MAX"
        />
        <Button
          disabled={!startParam.trim()}
          onClick={() => setPreview(launchIntentLabel(parseStartParam(startParam.trim())))}
        >
          Проверить ссылку
        </Button>
        {preview && <Typography.Text className="muted-text">Маршрут: {preview}</Typography.Text>}
        <Typography.Text className="muted-text">
          В следующих вехах значение откроет нужный экран приглашения или помощи.
        </Typography.Text>
      </Flex>
    </Flex>
  );
}
