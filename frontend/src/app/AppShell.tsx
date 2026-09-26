import { useEffect, type ReactNode } from 'react';
import { showBackButton } from '../platform/maxBridge';
import { ToastProvider } from '../components/ToastProvider';
import { AppIcon } from '../components/UiPrimitives';

interface AppShellProps {
  children: ReactNode;
  title?: string;
  onBack?: () => void;
  hideHeader?: boolean;
}

export function AppShell({ children, title = 'Рядом', onBack, hideHeader = false }: AppShellProps) {
  useEffect(() => {
    if (!onBack) return undefined;
    return showBackButton(onBack);
  }, [onBack]);

  return (
    <ToastProvider><div className="app-shell">
      <div className="app-shell__panel">
        {!hideHeader && <header className="app-topbar">
          {onBack ? <button type="button" className="ui-icon-button" aria-label="Назад" title="Назад" onClick={onBack}><AppIcon name="back" /></button> : <span className="app-topbar__spacer" />}
          <div className="app-topbar__title">{title}</div>
          <span className="app-topbar__spacer" />
        </header>}
        <main className="app-shell__content">{children}</main>
      </div>
    </div></ToastProvider>
  );
}
