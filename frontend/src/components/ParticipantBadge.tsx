import { Typography } from '@maxhub/max-ui';
import type { AssistParticipant } from '../api/client';

export function ParticipantBadge({ participant }: { participant: AssistParticipant }) {
  if (!participant.badge) return null;
  return <Typography.Text className="participant-badge">{participant.badge.label}{participant.badge.verified ? ' ✓' : ''}</Typography.Text>;
}
