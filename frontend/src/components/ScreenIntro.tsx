import type { ReactNode } from 'react';

interface ScreenIntroProps {
  eyebrow?: string;
  title: string;
  description?: string;
  meta?: string;
}

export function ScreenIntro({ eyebrow, title, description, meta }: ScreenIntroProps) {
  return (
    <div className="screen-intro">
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <h1>{title}</h1>
      {description && <p className="screen-intro__description">{description}</p>}
      {meta && <div className="screen-intro__meta">{meta}</div>}
    </div>
  );
}

export function SectionHeading({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="section-heading">
      <h2>{title}</h2>
      {action}
    </div>
  );
}

export function StatusMark({ tone = 'neutral' }: { tone?: 'neutral' | 'positive' | 'attention' }) {
  return <span className={`status-mark status-mark--${tone}`} aria-hidden="true" />;
}
