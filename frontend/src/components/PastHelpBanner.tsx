import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { getAccessToken, getPastHelp, type PastHelpFragment } from '../api/client';

function recordingUrl(fragment: PastHelpFragment): string | null {
  if (!fragment.audio_url) return null;
  return `${fragment.audio_url}${fragment.audio_url.includes('?') ? '&' : '?'}token=${encodeURIComponent(getAccessToken())}`;
}

export function PastHelpBanner({ serviceSessionId, stepId }: { serviceSessionId: string; stepId: string }) {
  const history = useQuery({ queryKey: ['past-help', serviceSessionId], queryFn: ({ signal }) => getPastHelp(serviceSessionId, signal), staleTime: 30_000 });
  const fragment = history.data?.steps[stepId]?.[0];
  if (!fragment) return null;
  const helper = fragment.helpers.map((item) => item.display_name).join(', ') || 'помощник';
  const url = recordingUrl(fragment);
  return <div className="notice notice--subtle"><Flex direction="column" gap={8}><Typography.Label>В прошлый раз на этом шаге помогал {helper}</Typography.Label><Typography.Text>{fragment.highlights ? `${fragment.highlights} подсказки сохранены для этого шага.` : 'Сохранён фрагмент прошлого объяснения.'}</Typography.Text>{url ? <audio controls preload="metadata" src={url} /> : <Button size="small" stretched variant="secondary" disabled>Аудиозапись недоступна</Button>}</Flex></div>;
}
