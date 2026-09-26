import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react';

export type AppIconName =
  | 'arrow' | 'arrow-right' | 'back' | 'check' | 'chevron' | 'circle' | 'clock' | 'document'
  | 'edit' | 'headset' | 'history' | 'home' | 'info' | 'link' | 'lock'
  | 'frame' | 'microphone' | 'more' | 'people' | 'play' | 'pointer' | 'qr' | 'robot' | 'scan'
  | 'forward' | 'pause' | 'rewind' | 'shield' | 'trash' | 'warning' | 'x';

export function AppIcon({ name, className = '' }: { name: AppIconName; className?: string }) {
  const paths: Record<AppIconName, ReactNode> = {
    arrow: <><path d="M5 19 19 5" /><path d="M10 5h9v9" /></>,
    'arrow-right': <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    back: <path d="m15 18-6-6 6-6" />,
    check: <path d="m5 12.5 4.5 4.5L19 7" />,
    chevron: <path d="m9 6 6 6-6 6" />,
    circle: <circle cx="12" cy="12" r="8" />,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    document: <><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></>,
    edit: <><path d="M4 20h16" /><path d="m7 16.5 9.5-9.5 3 3-9.5 9.5H7z" /></>,
    frame: <rect x="4" y="5.5" width="16" height="13" rx="2" />,
    forward: <><path d="m13 7 6 5-6 5z" /><path d="m5 7 6 5-6 5z" /></>,
    headset: <><path d="M4 15v-3a8 8 0 0 1 16 0v3" /><rect x="3" y="14" width="4" height="6" rx="1.5" /><rect x="17" y="14" width="4" height="6" rx="1.5" /><path d="M19 20c0 1.5-1.5 2-4 2h-2" /></>,
    history: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
    home: <><path d="m3.5 11 8.5-7 8.5 7" /><path d="M5.5 9.5V20h13V9.5" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
    link: <><path d="M10 14a4 4 0 0 0 5.7 0l3-3A4 4 0 0 0 13 5.3l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></>,
    lock: <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
    microphone: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" /></>,
    more: <><path d="M5 12h.01M12 12h.01M19 12h.01" /></>,
    people: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 19.5C2.5 16.3 5.4 14 9 14s6.5 2.3 6.5 5.5" /><circle cx="17" cy="9" r="2.5" /><path d="M17.5 13.6c2.4.3 4 2.1 4 4.6" /></>,
    pause: <><path d="M8.5 5v14M15.5 5v14" /></>,
    play: <path d="m8 5.5 11 6.5-11 6.5z" />,
    pointer: <path d="m5.5 3.5 13 6.5-5.5 2-2 5.5z" />,
    qr: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><path d="M14 14h3v3h-3zM18 18h3v3h-3zM14 20h2M20 14h1" /></>,
    robot: <><rect x="4.5" y="8" width="15" height="11" rx="4" /><path d="M12 4v4M9.5 13v1M14.5 13v1M2 13v2M22 13v2" /></>,
    rewind: <><path d="m11 7-6 5 6 5z" /><path d="m19 7-6 5 6 5z" /></>,
    scan: <><path d="M8 3H4a1 1 0 0 0-1 1v4M16 3h4a1 1 0 0 1 1 1v4M8 21H4a1 1 0 0 1-1-1v-4M16 21h4a1 1 0 0 0 1-1v-4" /><path d="M7 12h10" /></>,
    shield: <><path d="m12 3 8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /><path d="m9 12 2 2 4-4" /></>,
    trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5" /></>,
    warning: <><path d="m12 4 9 16H3z" /><path d="M12 10v4M12 17h.01" /></>,
    x: <><path d="m6 6 12 12M18 6 6 18" /></>,
  };
  return <svg className={`app-icon ${className}`.trim()} viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

export function AppInput({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`app-input ${className}`.trim()} {...props} />;
}

export function Surface({ children, className = '', tone = 'default' }: { children: ReactNode; className?: string; tone?: 'default' | 'blue' | 'green' | 'warning' }) {
  return <section className={`ui-surface ui-surface--${tone} ${className}`.trim()}>{children}</section>;
}

export function PersonRow({ name, meta, photoUrl, initials, tone = 'blue', online, trailing, large = false }: { name: ReactNode; meta?: ReactNode; photoUrl?: string | null; initials?: string; tone?: 'blue' | 'orange' | 'green' | 'purple' | 'agent'; online?: boolean; trailing?: ReactNode; large?: boolean }) {
  const fallback = initials || String(name).split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase();
  return <div className={`ui-person${large ? ' ui-person--large' : ''}`}>
    <span className={`ui-avatar ui-avatar--${tone}${large ? ' ui-avatar--large' : ''}`}>
      {photoUrl ? <img src={photoUrl} alt="" /> : fallback}
      {online && <span className="ui-presence" />}
    </span>
    <span className="ui-person__copy"><strong>{name}</strong>{meta && <span>{meta}</span>}</span>
    {trailing && <span className="ui-person__trailing">{trailing}</span>}
  </div>;
}

export function StatusScreen({ icon, tone = 'blue', title, description, children }: { icon: AppIconName; tone?: 'blue' | 'green' | 'orange' | 'red'; title: string; description?: ReactNode; children?: ReactNode }) {
  return <div className="ui-status-screen">
    <span className={`ui-status-icon ui-status-icon--${tone}`}><AppIcon name={icon} /></span>
    <h1>{title}</h1>
    {description && <p>{description}</p>}
    {children}
  </div>;
}

export function SegmentedControl<T extends string>({ value, options, onChange }: { value: T; options: Array<{ value: T; label: string }>; onChange: (value: T) => void }) {
  return <div className="ui-segmented" role="tablist">{options.map((option) => <button key={option.value} type="button" role="tab" aria-selected={value === option.value} className={value === option.value ? 'is-active' : ''} onClick={() => onChange(option.value)}>{option.label}</button>)}</div>;
}

export function ListRow({ icon, iconTone = 'blue', title, subtitle, trailing, onClick, className = '', disabled = false }: { icon?: AppIconName; iconTone?: 'blue' | 'green' | 'orange' | 'purple'; title: ReactNode; subtitle?: ReactNode; trailing?: ReactNode; onClick?: () => void; className?: string; disabled?: boolean }) {
  const content = <>{icon && <span className={`ui-tile ui-tile--${iconTone}`}><AppIcon name={icon} /></span>}<span className="ui-list-row__copy"><strong>{title}</strong>{subtitle && <span>{subtitle}</span>}</span>{trailing ?? (onClick ? <AppIcon name="chevron" className="ui-list-row__chevron" /> : null)}</>;
  if (onClick) return <button type="button" className={`ui-list-row ${className}`.trim()} disabled={disabled} onClick={onClick}>{content}</button>;
  return <div className={`ui-list-row ${className}`.trim()}>{content}</div>;
}

export function IconButton({ label, icon, tone = 'default', ...props }: { label: string; icon: AppIconName; tone?: 'default' | 'danger' } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'>) {
  return <button type="button" className={`ui-icon-button ui-icon-button--${tone}`} aria-label={label} title={label} {...props}><AppIcon name={icon} /></button>;
}

export function BottomNav({ active, onHome, onServices, onHistory, onHelpers }: { active: 'home' | 'services' | 'history' | 'helpers'; onHome: () => void; onServices: () => void; onHistory: () => void; onHelpers: () => void }) {
  const items: Array<{ id: typeof active; label: string; icon: AppIconName; action: () => void }> = [
    { id: 'home', label: 'Главная', icon: 'home', action: onHome },
    { id: 'services', label: 'Услуги', icon: 'document', action: onServices },
    { id: 'history', label: 'История', icon: 'history', action: onHistory },
    { id: 'helpers', label: 'Близкие', icon: 'people', action: onHelpers },
  ];
  return <nav className="ui-tabbar" aria-label="Разделы">{items.map((item) => <button key={item.id} type="button" className={active === item.id ? 'is-active' : ''} onClick={item.action}><AppIcon name={item.icon} /><span>{item.label}</span></button>)}</nav>;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} сек`;
  return `${Math.max(1, Math.round(seconds / 60))} мин`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return 'Дата не указана';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
}
