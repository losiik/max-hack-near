import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Button, Flex, Typography } from '@maxhub/max-ui';

export function AppDialog({ title, children, onClose, labelledBy = 'app-dialog-title' }: { title: string; children: ReactNode; onClose: () => void; labelledBy?: string }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusable = () => Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [href], select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') ?? []);
    const timer = window.setTimeout(() => (focusable()[0] ?? closeRef.current)?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { onClose(); return; }
      if (event.key !== 'Tab') return;
      const items = focusable();
      if (!items.length) { event.preventDefault(); return; }
      const first = items[0]; const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => { window.clearTimeout(timer); window.removeEventListener('keydown', onKeyDown); previouslyFocused?.focus(); };
  }, [onClose]);
  const portalTarget = document.querySelector<HTMLElement>('[class*="MaxUI__"]') ?? document.body;
  return createPortal(
    <div className="app-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="app-dialog" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
        <Flex direction="column" gap={12}>
          <Typography.Title id={labelledBy}>{title}</Typography.Title>
          {children}
          <button ref={closeRef} className="visually-hidden" aria-label="Закрыть диалог" onClick={onClose} />
        </Flex>
      </section>
    </div>, portalTarget,
  );
}

export function ConfirmDialog({ title, description, confirmLabel, pending = false, destructive = false, onCancel, onConfirm }: { title: string; description: string; confirmLabel: string; pending?: boolean; destructive?: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <AppDialog title={title} onClose={pending ? () => undefined : onCancel}>
    <Typography.Text>{description}</Typography.Text>
    <Flex gap={8} className="dialog-actions">
      <Button size="small" variant="ghost" disabled={pending} onClick={onCancel}>Отмена</Button>
      <Button size="small" variant={destructive ? 'destructive' : 'primary'} loading={pending} disabled={pending} onClick={onConfirm}>{confirmLabel}</Button>
    </Flex>
  </AppDialog>;
}
