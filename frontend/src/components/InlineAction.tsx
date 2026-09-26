import { Button, Flex, Typography } from '@maxhub/max-ui';
import type { ReactNode } from 'react';

type ActionVariant = 'primary' | 'secondary' | 'destructive' | 'ghost';

interface InlineActionProps {
  title: string;
  description?: ReactNode;
  action: string;
  variant?: ActionVariant;
  disabled?: boolean;
  loading?: boolean;
  onClick: () => void;
}

/** Compact MAX UI action: context on the left, a single unambiguous action on the right. */
export function InlineAction({ title, description, action, variant = 'primary', disabled = false, loading = false, onClick }: InlineActionProps) {
  return <div className="inline-action">
    <Flex direction="column" gap={2} className="inline-action__copy">
      <Typography.Label>{title}</Typography.Label>
      {description && <Typography.Text className="muted-text">{description}</Typography.Text>}
    </Flex>
    <Button size="small" variant={variant} disabled={disabled} loading={loading} onClick={onClick}>{action}</Button>
  </div>;
}
