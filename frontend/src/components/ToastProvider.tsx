import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

type ToastTone = 'default' | 'error';
const ToastContext = createContext<(message: string, tone?: ToastTone) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ message: string; tone: ToastTone } | null>(null);
  const show = useCallback((message: string, tone: ToastTone = 'default') => {
    setToast({ message, tone });
    window.setTimeout(() => setToast(null), 4_000);
  }, []);
  const value = useMemo(() => show, [show]);
  return <ToastContext.Provider value={value}>{children}{toast && createPortal(<div className={`app-toast app-toast--${toast.tone}`} role="status">{toast.message}</div>, document.body)}</ToastContext.Provider>;
}

export function useToast(): (message: string, tone?: ToastTone) => void {
  return useContext(ToastContext);
}
