import { useEffect, useMemo, useState } from 'react';
import type { ProjectedState } from '../api/client';
import { hapticLight } from '../platform/maxBridge';
import type { AssistPointer } from '../realtime/assistStore';

type Annotation = ProjectedState['annotations'][number];
type Positioned = Annotation & { left: number; top: number; width: number; height: number };

function targetFor(elementId: string): HTMLElement | null {
  const escaped = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(elementId) : elementId.replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  return document.querySelector<HTMLElement>(`[data-assist-id="${escaped}"]`);
}

function isAlive(annotation: Annotation): boolean {
  return !annotation.expires_at || Date.parse(annotation.expires_at) > Date.now();
}

export function AnnotationLayer({ annotations, pointer, autoScroll = false }: { annotations: Annotation[]; pointer: AssistPointer | null; autoScroll?: boolean }) {
  const [version, setVersion] = useState(0);
  const [now, setNow] = useState(Date.now());
  const seen = useMemo(() => new Set<string>(), []);

  useEffect(() => {
    const update = () => setVersion((value) => value + 1);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => { window.removeEventListener('resize', update); window.removeEventListener('scroll', update, true); };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    annotations.filter(isAlive).forEach((annotation) => {
      if (seen.has(annotation.id)) return;
      seen.add(annotation.id);
      hapticLight();
      if (!autoScroll) return;
      const target = targetFor(annotation.element_id);
      if (!target) return;
      const rect = target.getBoundingClientRect();
      if (rect.top < 0 || rect.bottom > window.innerHeight) target.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
  }, [annotations, autoScroll, seen]);

  const positioned = annotations.filter(isAlive).flatMap((annotation) => {
    const rect = targetFor(annotation.element_id)?.getBoundingClientRect();
    return rect ? [{ ...annotation, left: rect.left, top: rect.top, width: rect.width, height: rect.height }] : [];
  });
  const pointerPosition = pointer && (() => {
    const rect = targetFor(pointer.elementId)?.getBoundingClientRect();
    return rect ? { left: rect.left + rect.width * pointer.relX, top: rect.top + rect.height * pointer.relY } : null;
  })();

  void version;
  void now;
  return <div className="annotation-layer" aria-live="polite">
    {positioned.map((annotation) => (
      <div key={annotation.id} className={`annotation annotation--${annotation.kind}`} style={{ left: annotation.left, top: annotation.top, width: annotation.width, height: annotation.height }}>
        <span className="annotation__label">{annotation.author.display_name}: {annotation.label || 'показывает сюда'}</span>
      </div>
    ))}
    {pointerPosition && <span className="annotation-pointer" style={pointerPosition} aria-label="Указка помощника" />}
  </div>;
}
