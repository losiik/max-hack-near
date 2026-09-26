import { Button, Flex, Typography } from '@maxhub/max-ui';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { getConsultationRecording, getPastHelp, type PastHelpFragment } from '../api/client';
import { AppIcon } from './UiPrimitives';

export function PastHelpBanner({ serviceSessionId, stepId }: { serviceSessionId: string; stepId: string }) {
  const history = useQuery({ queryKey: ['past-help', serviceSessionId], queryFn: ({ signal }) => getPastHelp(serviceSessionId, signal), staleTime: 30_000 });
  const fragment = history.data?.steps[stepId]?.[0];
  const [expanded, setExpanded] = useState(false);
  const recording = useQuery({ queryKey: ['consultation-recording', fragment?.assist_session_id ?? ''], queryFn: ({ signal }) => getConsultationRecording(fragment!.assist_session_id, signal), enabled: expanded && Boolean(fragment?.has_audio), retry: false });
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!recording.data) { setRecordingUrl(null); return; }
    const url = URL.createObjectURL(recording.data);
    setRecordingUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [recording.data]);
  if (!fragment) return null;
  const helper = fragment.helpers.map((item) => item.display_name).join(', ') || 'помощник';
  return <section className="past-help">
    <Button size="small" variant="ghost" className="past-help__toggle" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
      <span className="ui-tile ui-tile--green"><AppIcon name="history" /></span><span className="past-help__title"><strong>Как вы решали это раньше</strong><small>Сохранены подсказки от {helper}</small></span><AppIcon name="chevron" className={`past-help__chevron${expanded ? ' past-help__chevron--open' : ''}`} />
    </Button>
    {expanded && <Flex direction="column" gap={8} className="past-help__content">
      <Typography.Label>В прошлый раз на этом шаге помогал {helper}</Typography.Label>
      <Typography.Text>{fragment.highlights ? `${fragment.highlights} подсказки сохранены для этого шага.` : 'Сохранён фрагмент прошлого объяснения.'}</Typography.Text>
      {recordingUrl ? <audio controls preload="metadata" src={recordingUrl} /> : <Typography.Text className="muted-text">{recording.isLoading ? 'Загружаем аудиозапись…' : 'Аудиозапись недоступна'}</Typography.Text>}
    </Flex>}
  </section>;
}
