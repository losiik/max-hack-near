import { useEffect, type ReactNode } from 'react';
import { Flex, Typography } from '@maxhub/max-ui';
import { showBackButton } from '../platform/maxBridge';
import { ToastProvider } from '../components/ToastProvider';

interface AppShellProps {
  children: ReactNode;
  title?: string;
  onBack?: () => void;
}

export function AppShell({ children, title = 'Рядом', onBack }: AppShellProps) {
  useEffect(() => {
    if (!onBack) return undefined;
    return showBackButton(onBack);
  }, [onBack]);

  return (
    <ToastProvider><div className="app-shell">
      <div className="app-shell__panel">
        <Flex direction="column" gap={12}>
          <header className="app-shell__header">
            <div className="brand-lockup" aria-label={title}>
              <span className="brand-lockup__mark">Р</span>
              <Typography.Text className="brand-lockup__name">{title}</Typography.Text>
            </div>
          </header>
          <main>{children}</main>
        </Flex>
      </div>
    </div></ToastProvider>
  );
}
