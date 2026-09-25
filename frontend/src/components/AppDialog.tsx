import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Button, Flex, Typography } from '@maxhub/max-ui';

export function AppDialog({ title, children, onClose, labelledBy = 'app-dialog-title' }: { title: string; children: ReactNode; onClose: () => void; labelledBy?: string }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);
  return createPortal(
    <div className="app-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="app-dialog" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
        <Flex direction="column" gap={12}>
          <Typography.Title id={labelledBy}>{title}</Typography.Title>
          {children}
          <button ref={closeRef} className="visually-hidden" aria-label="Закрыть диалог" onClick={onClose} />
        </Flex>
      </section>
    </div>, document.body,
  );
}

export function ConfirmDialog({ title, description, confirmLabel, pending = false, destructive = false, onCancel, onConfirm }: { title: string; description: string; confirmLabel: string; pending?: boolean; destructive?: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <AppDialog title={title} onClose={pending ? () => undefined : onCancel}>
    <Typography.Text>{description}</Typography.Text>
    <Flex direction="column" gap={8}>
      <Button size="small" stretched variant={destructive ? 'destructive' : 'primary'} loading={pending} disabled={pending} onClick={onConfirm}>{confirmLabel}</Button>
      <Button size="small" stretched variant="ghost" disabled={pending} onClick={onCancel}>Отмена</Button>
    </Flex>
  </AppDialog>;
}
