'use client';
import { useEffect, useId, useRef, type ReactNode, type ButtonHTMLAttributes } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion, useMotionValue, useSpring } from 'motion/react';
import { ArrowUpRight, X, Loader2, AlertCircle, Sun, Moon, Inbox } from 'lucide-react';
import { cn, initials } from '@/lib/utils';
import { usePreferences } from './providers';

export function Logo({ compact = false, className = '', onClick }: { compact?: boolean; className?: string; onClick?: () => void }) {
  return <span className={cn('logo', className)} onClick={onClick}><svg className="brand-symbol" width="29" height="29" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M3 24V7.5L10 12v16L3 24Z" fill="currentColor"/><path d="m12 5 7 4.5V26l-7-4.5V5Z" fill="currentColor"/><path d="m21 10 8-5v16.5L21 26V10Z" fill="currentColor"/></svg>{!compact && <span>momentum<span className="logo-period">.</span></span>}</span>;
}
export function Magnetic({ children, className = '' }: { children: ReactNode; className?: string }) {
  const { reduced } = usePreferences(); const x = useMotionValue(0); const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 18 }); const sy = useSpring(y, { stiffness: 220, damping: 18 });
  return <motion.div className={cn('magnetic', className)} style={{ x: sx, y: sy }} onPointerMove={event => { if (reduced || event.pointerType !== 'mouse') return; const rect = event.currentTarget.getBoundingClientRect(); x.set((event.clientX - rect.left - rect.width/2)*0.12); y.set((event.clientY - rect.top - rect.height/2)*0.2); }} onPointerLeave={() => { x.set(0); y.set(0); }}>{children}</motion.div>;
}
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { href?: string; variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; icon?: ReactNode; loading?: boolean; small?: boolean };
export function Button({ children, href, variant = 'primary', icon, loading, small, className, disabled, ...props }: ButtonProps) {
  const content = <>{loading ? <Loader2 size={16} className="spin"/> : null}{children}{icon || (!loading && variant === 'primary' ? <ArrowUpRight size={16}/> : null)}</>;
  const classes = cn('button', variant, small && 'small', className);
  return <Magnetic>{href ? <Link href={href} className={classes} aria-disabled={disabled || loading} onClick={e => { if (disabled || loading) e.preventDefault(); }}>{content}</Link> : <button className={classes} disabled={disabled || loading} {...props}>{content}</button>}</Magnetic>;
}
export function IconButton({ children, label, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) { return <button type="button" aria-label={label} title={label} className={cn('icon-button', className)} {...props}>{children}</button>; }
export function ThemeToggle() { const { resolvedTheme, setTheme } = usePreferences(); return <IconButton label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`} onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}>{resolvedTheme === 'dark' ? <Sun size={17}/> : <Moon size={17}/>}</IconButton>; }
export function Badge({ children, tone = 'neutral', dot = false, className }: { children: ReactNode; tone?: string; dot?: boolean; className?: string }) { return <span className={cn('badge', `badge-${tone}`, className)}>{dot && <span className="status-dot"/>}{children}</span>; }
export function Avatar({ name, color, size = 'normal' }: { name: string; color?: string; size?: 'small' | 'normal' | 'large' }) { return <span className={cn('avatar', `avatar-${size}`)} style={{ '--avatar-color': color || '#5B7CFF' } as React.CSSProperties} title={name}>{initials(name)}</span>; }
export function AvatarGroup({ people }: { people: { name: string; color: string }[] }) { return <div className="avatar-group">{people.slice(0, 4).map((p, i) => <Avatar key={p.name+i} name={p.name} color={p.color} size="small"/>)}{people.length > 4 && <span className="avatar avatar-small">+{people.length-4}</span>}</div>; }
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) { return <div className={cn('eyebrow', className)}><span className="eyebrow-line"/>{children}</div>; }
export function Reveal({ children, className, delay = 0, y = 24 }: { children: ReactNode; className?: string; delay?: number; y?: number }) { const { reduced } = usePreferences(); return <motion.div initial={{ opacity: 0, y: reduced ? 0 : y }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.12 }} transition={{ duration: reduced ? 0.15 : 0.65, delay: reduced ? 0 : delay, ease: [0.22,1,0.36,1] }} className={className}>{children}</motion.div>; }
export function Modal({ open, onClose, title, description, children, wide = false }: { open: boolean; onClose: () => void; title: string; description?: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null); const titleId = useId(); const closeRef = useRef(onClose); closeRef.current = onClose;
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement; const overflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
    const timeout = setTimeout(() => ref.current?.querySelector<HTMLElement>('input,textarea,select,button,[tabindex="0"]')?.focus(), 40);
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); closeRef.current(); }
      if (event.key === 'Tab') {
        const items = ref.current?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),textarea,select,[tabindex="0"]');
        if (!items?.length) return; const first = items[0], last = items[items.length-1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', handler);
    return () => { clearTimeout(timeout); document.body.style.overflow = overflow; document.removeEventListener('keydown', handler); previous?.focus(); };
  }, [open]);
  return <AnimatePresence>{open && <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}><motion.div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} className={cn('modal', wide && 'modal-wide')} initial={{ opacity: 0, y: 18, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8 }} transition={{ duration: 0.2 }}><div className="modal-heading"><div><h2 id={titleId}>{title}</h2>{description && <p>{description}</p>}</div><IconButton label="Close dialog" onClick={onClose}><X size={20}/></IconButton></div>{children}</motion.div></motion.div>}</AnimatePresence>;
}
export function EmptyState({ title, description, action, icon }: { title: string; description: string; action?: ReactNode; icon?: ReactNode }) { return <div className="empty-state"><div className="empty-icon">{icon || <Inbox size={25}/>}</div><h3>{title}</h3><p>{description}</p>{action}</div>; }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) { return <div className="error-state" role="alert"><AlertCircle size={22}/><div><strong>We couldn’t load this view.</strong><p>{message}</p></div>{retry && <Button variant="secondary" small onClick={retry}>Try again</Button>}</div>; }
export function Skeleton({ rows = 4 }: { rows?: number }) { return <div className="skeleton-wrap" aria-label="Loading" role="status">{Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" style={{ width: `${100-(i%3)*12}%` }}/>)}</div>; }
export function PageHeading({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) { return <div className="page-heading"><div>{eyebrow && <span className="page-eyebrow">{eyebrow}</span>}<h1>{title}</h1><p>{description}</p></div>{actions && <div className="page-actions">{actions}</div>}</div>; }
export function Field({ label, hint, children, className }: { label: string; hint?: string; children: ReactNode; className?: string }) { return <label className={cn('field', className)}><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>; }
export function ProgressBar({ value, color }: { value: number; color?: string }) { return <div className="progress-track" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${Math.min(100, Math.max(0, value))}%`, background: color }}/></div>; }
