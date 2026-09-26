import { useEffect, useRef, type ReactNode } from 'react';
import { showBackButton } from '../platform/maxBridge';
import { ToastProvider } from '../components/ToastProvider';

interface AppShellProps {
  children: ReactNode;
  title?: string;
  onBack?: () => void;
  hideHeader?: boolean;
}

export function AppShell({ children, title = 'Рядом', onBack, hideHeader = false }: AppShellProps) {
  const onBackRef = useRef(onBack);

  useEffect(() => {
    onBackRef.current = onBack;
  }, [onBack]);

  useEffect(() => {
    if (!onBackRef.current) return undefined;
    return showBackButton(() => onBackRef.current?.());
  }, [Boolean(onBack)]);

  return (
    <ToastProvider><div className="app-shell">
      <div className="app-shell__panel">
        {!hideHeader && <header className="app-topbar">
          <span className="app-topbar__spacer" aria-hidden="true" />
          <div className="app-topbar__title">{title}</div>
          <span className="app-topbar__spacer" />
        </header>}
        <main className="app-shell__content">{children}</main>
      </div>
    </div></ToastProvider>
  );
}
