import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { getAccessToken, getPastHelp, type PastHelpFragment } from '../api/client';

function recordingUrl(fragment: PastHelpFragment): string | null {
  if (!fragment.audio_url) return null;
  return `${fragment.audio_url}${fragment.audio_url.includes('?') ? '&' : '?'}token=${encodeURIComponent(getAccessToken())}`;
}

export function PastHelpBanner({ serviceSessionId, stepId }: { serviceSessionId: string; stepId: string }) {
  const history = useQuery({ queryKey: ['past-help', serviceSessionId], queryFn: ({ signal }) => getPastHelp(serviceSessionId, signal), staleTime: 30_000 });
  const fragment = history.data?.steps[stepId]?.[0];
  const [expanded, setExpanded] = useState(false);
  if (!fragment) return null;
  const helper = fragment.helpers.map((item) => item.display_name).join(', ') || 'помощник';
  const url = recordingUrl(fragment);
  return <section className="past-help">
    <Button size="small" variant="ghost" className="past-help__toggle" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
      <span>Подсказки</span><span className={`past-help__chevron${expanded ? ' past-help__chevron--open' : ''}`} aria-hidden="true">›</span>
    </Button>
    {expanded && <Flex direction="column" gap={8} className="past-help__content">
      <Typography.Label>В прошлый раз на этом шаге помогал {helper}</Typography.Label>
      <Typography.Text>{fragment.highlights ? `${fragment.highlights} подсказки сохранены для этого шага.` : 'Сохранён фрагмент прошлого объяснения.'}</Typography.Text>
      {url ? <audio controls preload="metadata" src={url} /> : <Typography.Text className="muted-text">Аудиозапись недоступна</Typography.Text>}
    </Flex>}
  </section>;
}
