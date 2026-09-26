import { useEffect, useRef, useState } from 'react';
import { AppIcon } from './UiPrimitives';

export interface SelectOption { value: string; label: string }

interface SyncedSelectProps {
  elementId: string;
  options: SelectOption[];
  value: string | null;
  ariaLabel?: string;
  placeholder?: string;
  readOnly?: boolean;
  shared?: boolean;
  open?: boolean;
  scrollTop?: number;
  viewportHeight?: number;
  onChange?: (value: string | null) => void;
  onOpenChange?: (open: boolean) => void;
  onScrollTop?: (scrollTop: number) => void;
  onViewportHeight?: (height: number) => void;
}

export function SyncedSelect({
  elementId,
  options,
  value,
  ariaLabel,
  placeholder = 'Выберите вариант',
  readOnly = false,
  shared = false,
  open: sharedOpen,
  scrollTop: sharedScrollTop,
  viewportHeight,
  onChange,
  onOpenChange,
  onScrollTop,
  onViewportHeight,
}: SyncedSelectProps) {
  const [localOpen, setLocalOpen] = useState(false);
  const [localScrollTop, setLocalScrollTop] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const lastSentAt = useRef(0);
  const scrollTimer = useRef<number | undefined>(undefined);
  const pendingScrollTop = useRef(0);
  const viewportHeightCallback = useRef(onViewportHeight);
  const open = shared ? Boolean(sharedOpen) : localOpen;
  const scrollTop = shared ? (sharedScrollTop ?? 0) : localScrollTop;
  const selected = options.find((option) => option.value === value);

  useEffect(() => { viewportHeightCallback.current = onViewportHeight; }, [onViewportHeight]);

  useEffect(() => {
    if (open && listRef.current && Math.abs(listRef.current.scrollTop - scrollTop) > 1) {
      listRef.current.scrollTop = scrollTop;
    }
  }, [open, scrollTop]);

  useEffect(() => () => window.clearTimeout(scrollTimer.current), []);

  useEffect(() => {
    const list = listRef.current;
    if (!open || readOnly || !list || !viewportHeightCallback.current) return;
    let lastHeight = 0;
    const reportHeight = () => {
      const height = list.clientHeight;
      if (height > 0 && Math.abs(height - lastHeight) > 1) {
        lastHeight = height;
        viewportHeightCallback.current?.(height);
      }
    };
    reportHeight();
    const observer = new ResizeObserver(reportHeight);
    observer.observe(list);
    return () => observer.disconnect();
  }, [open, readOnly]);

  useEffect(() => {
    if (!open || readOnly) return;
    const closeOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) onOpenChange?.(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onOpenChange?.(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open, readOnly, onOpenChange]);

  function setOpen(next: boolean) {
    if (!next) {
      window.clearTimeout(scrollTimer.current);
      scrollTimer.current = undefined;
    }
    if (shared) onOpenChange?.(next);
    else setLocalOpen(next);
    if (next) {
      setLocalScrollTop(0);
      if (!shared && listRef.current) listRef.current.scrollTop = 0;
    }
  }

  function updateScrollTop(next: number) {
    if (!shared) setLocalScrollTop(next);
    if (readOnly || !onScrollTop) return;
    pendingScrollTop.current = next;
    const now = Date.now();
    const remaining = 70 - (now - lastSentAt.current);
    if (remaining <= 0) {
      window.clearTimeout(scrollTimer.current);
      scrollTimer.current = undefined;
      lastSentAt.current = now;
      onScrollTop(next);
      return;
    }
    if (scrollTimer.current === undefined) {
      scrollTimer.current = window.setTimeout(() => {
        scrollTimer.current = undefined;
        lastSentAt.current = Date.now();
        onScrollTop(pendingScrollTop.current);
      }, remaining);
    }
  }

  return (
    <div className={`synced-select${open ? ' is-open' : ''}${readOnly ? ' is-readonly' : ''}`} ref={rootRef} data-select-id={elementId}>
      <button
        type="button"
        className="synced-select__trigger"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => { if (!readOnly) setOpen(!open); }}
      >
        <span className={selected ? '' : 'synced-select__placeholder'}>{selected?.label ?? placeholder}</span>
        <AppIcon name="chevron" />
      </button>
      {open && <div
        className="synced-select__options"
        style={readOnly && viewportHeight ? { maxHeight: `${viewportHeight}px` } : undefined}
        role="listbox"
        aria-label="Варианты ответа"
        ref={listRef}
        onScroll={(event) => updateScrollTop(event.currentTarget.scrollTop)}
      >
        {options.map((option) => {
          const isSelected = option.value === value;
          return <button
            type="button"
            role="option"
            aria-selected={isSelected}
            className={`synced-select__option${isSelected ? ' is-selected' : ''}`}
            key={option.value}
            tabIndex={readOnly ? -1 : 0}
            onClick={() => {
              if (readOnly) return;
              onChange?.(option.value);
              setOpen(false);
            }}
          >
            <span title={option.label}>{option.label}</span>
            {isSelected && <AppIcon name="check" />}
          </button>;
        })}
      </div>}
    </div>
  );
}
