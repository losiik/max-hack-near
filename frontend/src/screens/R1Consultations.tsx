import { Button, CellList, CellSimple, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { consultationsQuery, queryKeys } from '../api/queries';
import { ScreenIntro } from '../components/ScreenIntro';

export function R1Consultations({ as: initialRole, onOpen }: { as: 'owner' | 'helper'; onOpen: (id: string) => void }) {
  const [as, setAs] = useState(initialRole);
  const list = useQuery({ queryKey: queryKeys.consultations(as), queryFn: consultationsQuery });
  return <Flex direction="column" gap={12}><ScreenIntro eyebrow="Помощь рядом" title="Мои консультации" /><Flex gap={8}><Button size="small" stretched variant={as === 'owner' ? 'primary' : 'secondary'} onClick={() => setAs('owner')}>Мне помогали</Button><Button size="small" stretched variant={as === 'helper' ? 'primary' : 'secondary'} onClick={() => setAs('helper')}>Я помогал</Button></Flex>{list.isLoading && <Typography.Text>Загружаем историю…</Typography.Text>}{list.error && <div className="notice notice--error">{list.error instanceof Error ? list.error.message : 'Не удалось загрузить историю'}</div>}{list.data?.length === 0 && <Typography.Text className="muted-text">Консультаций пока нет.</Typography.Text>}<CellList mode="island" filled>{list.data?.map((item) => <CellSimple key={item.assist_session_id} surface="island" title={item.service.title} subtitle={`${as === 'owner' ? item.helpers.map((helper) => helper.display_name).join(', ') || 'Помощник' : item.owner_display_name || 'Владелец'} · ${item.steps_completed ?? 0} из ${item.total_steps} шагов`} after={<Button size="small" variant="secondary" onClick={() => onOpen(item.assist_session_id)}>Открыть</Button>} />)}</CellList></Flex>;
}
