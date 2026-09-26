import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

type ToastTone = 'default' | 'error';
const ToastContext = createContext<(message: string, tone?: ToastTone) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ message: string; tone: ToastTone } | null>(null);
  const timerRef = useRef<number | null>(null);
  const show = useCallback((message: string, tone: ToastTone = 'default') => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    setToast({ message, tone });
    timerRef.current = window.setTimeout(() => {
      setToast(null);
      timerRef.current = null;
    }, 4_000);
  }, []);
  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
  }, []);
  const value = useMemo(() => show, [show]);
  // Keep the toast inside the Max UI theme root so its light/dark variables
  // remain available, while the fixed layer and high z-index keep it above
  // screens and dialogs.
  const portalTarget = document.querySelector<HTMLElement>('.app-shell') ?? document.querySelector<HTMLElement>('[class*="MaxUI__"]') ?? document.body;
  return <ToastContext.Provider value={value}>{children}{toast && createPortal(<div className={`app-toast app-toast--${toast.tone}`} role="status" aria-live="polite"><span aria-hidden="true">{toast.tone === 'error' ? '!' : '✓'}</span><span>{toast.message}</span></div>, portalTarget)}</ToastContext.Provider>;
}

export function useToast(): (message: string, tone?: ToastTone) => void {
  return useContext(ToastContext);
}
