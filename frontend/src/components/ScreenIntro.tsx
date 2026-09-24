import { Flex, Typography } from '@maxhub/max-ui';
import type { ReactNode } from 'react';

interface ScreenIntroProps {
  eyebrow?: string;
  title: string;
  description?: string;
  meta?: string;
}

export function ScreenIntro({ eyebrow, title, description, meta }: ScreenIntroProps) {
  return (
    <Flex direction="column" gap={6} className="screen-intro">
      {eyebrow && <Typography.Label className="eyebrow">{eyebrow}</Typography.Label>}
      <Typography.Headline>{title}</Typography.Headline>
      {description && <Typography.Body className="screen-intro__description">{description}</Typography.Body>}
      {meta && <Typography.Text className="screen-intro__meta">{meta}</Typography.Text>}
    </Flex>
  );
}

export function SectionHeading({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <Flex align="center" justify="space-between" gap={12} className="section-heading">
      <Typography.Title>{title}</Typography.Title>
      {action}
    </Flex>
  );
}

export function StatusMark({ tone = 'neutral' }: { tone?: 'neutral' | 'positive' | 'attention' }) {
  return <span className={`status-mark status-mark--${tone}`} aria-hidden="true" />;
}
