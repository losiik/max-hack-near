import { useState } from 'react';
import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useMutation, useQuery } from '@tanstack/react-query';
import { loginWithDev, type AuthUser, type DevUser } from '../api/client';
import { devOutboxQuery, devUsersQuery, queryKeys } from '../api/queries';
import { launchIntentLabel, parseStartParam } from '../platform/startParam';
import { ScreenIntro, SectionHeading } from '../components/ScreenIntro';
import { AppIcon, ListRow, PersonRow, Surface } from '../components/UiPrimitives';

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
    <div className="ui-page">
      <ScreenIntro eyebrow="Только локальная разработка" title="Режим разработки" description="Выберите пользователя, чтобы проверить сценарий без MAX." />

      {(error || users.error) && <div className="notice notice--error">{error || (users.error as Error).message}</div>}

      {!selected && <section className="home-section">
        <SectionHeading title="Пользователь" />
        {users.isLoading && <Typography.Text>Загружаем список…</Typography.Text>}
        <div className="ui-list">{users.data?.map((user) => <ListRow key={user.user_key} icon="people" title={user.display_name} subtitle={user.role_hint} disabled={login.isPending} onClick={() => void chooseUser(user)} />)}</div>
      </section>}

      {selected && <><Surface tone="blue"><PersonRow name={selected.display_name} meta="Текущий тестовый пользователь" photoUrl={selected.photo_url} /><Button size="small" stretched onClick={onHome}>Открыть приложение<AppIcon name="arrow-right" /></Button></Surface><section className="home-section"><SectionHeading title="Сообщения бота" />{outbox.data?.length === 0 && <Typography.Text className="muted-text">Сообщений пока нет.</Typography.Text>}{outbox.data?.map((message) => <Surface key={message.id}><Flex direction="column" gap={8}><Typography.Text>{message.text}</Typography.Text>{message.buttons.map((button, index) => button.start_param ? <Button key={`${button.text}-${index}`} size="small" stretched variant="secondary" onClick={() => onLaunch(button.start_param!)}>{button.text}</Button> : <Typography.Text key={`${button.text}-${index}`} className="muted-text">{button.text}</Typography.Text>)}</Flex></Surface>)}</section></>}

      <Surface>
        <SectionHeading title="Проверить deep link" />
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
      </Surface>
    </div>
  );
}
