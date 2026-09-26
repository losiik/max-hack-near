import { useState } from 'react';
import { Button, Flex, Panel, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery } from '@tanstack/react-query';
import { loginWithDev, type AuthUser, type DevUser } from '../api/client';
import { devOutboxQuery, devUsersQuery, queryKeys } from '../api/queries';
import { launchIntentLabel, parseStartParam } from '../platform/startParam';

interface D1Props {
  onLogin: (user: AuthUser) => void;
  onLaunch: (startParam: string) => void;
  onHome: () => void;
}

export function D1({ onLogin, onLaunch, onHome }: D1Props) {
  const [startParam, setStartParam] = useState('');
  const [preview, setPreview] = useState('');
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<AuthUser | null>(null);
  const users = useQuery({ queryKey: queryKeys.devUsers(), queryFn: devUsersQuery });
  const login = useMutation({ mutationFn: loginWithDev });
  const outbox = useQuery({ queryKey: queryKeys.devOutbox(), queryFn: devOutboxQuery, enabled: Boolean(selected), refetchInterval: selected ? 3_000 : false });

  async function chooseUser(user: DevUser) {
    setError('');
    try {
      const response = await login.mutateAsync(user.user_key);
      onLogin(response.user);
      setSelected(response.user);
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

      {!selected && <Flex direction="column" gap={10}>
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
      </Flex>}

      {selected && <Flex direction="column" gap={10}><Typography.Label>Вы вошли как {selected.display_name}</Typography.Label><Button size="small" stretched onClick={onHome}>Открыть приложение</Button><Typography.Label>Сообщения бота</Typography.Label>{outbox.data?.length === 0 && <Typography.Text className="muted-text">Сообщений пока нет.</Typography.Text>}{outbox.data?.map((message) => <div className="notice" key={message.id}><Flex direction="column" gap={8}><Typography.Text>{message.text}</Typography.Text>{message.buttons.map((button, index) => button.start_param ? <Button key={`${button.text}-${index}`} size="small" stretched variant="secondary" onClick={() => onLaunch(button.start_param!)}>{button.text}</Button> : <Typography.Text key={`${button.text}-${index}`} className="muted-text">{button.text}</Typography.Text>)}</Flex></div>)}</Flex>}

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
          onClick={() => { setPreview(launchIntentLabel(parseStartParam(startParam.trim()))); if (selected) onLaunch(startParam.trim()); }}
        >
          Проверить ссылку
        </Button>
        {preview && <Typography.Text className="muted-text">Маршрут: {preview}</Typography.Text>}
      </Flex>
    </Flex>
  );
}
