'use client';
import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import { MotionConfig } from 'motion/react';
import { Check, AlertCircle, X, Info } from 'lucide-react';
import { api, patch } from '@/lib/api';
import type { User, Capabilities } from '@/lib/../types';

type Theme = 'dark' | 'light' | 'system';
type Motion = 'full' | 'reduced' | 'system';
const PreferencesContext = createContext<{ theme: Theme; resolvedTheme: string; setTheme: (theme: Theme) => void; motion: Motion; reduced: boolean; setMotion: (motion: Motion) => void; syncUser: (user: User) => void } | null>(null);
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [theme, updateTheme] = useState<Theme>('system');
  const [motion, updateMotion] = useState<Motion>('system');
  const [systemDark, setSystemDark] = useState(true);
  const [systemReduced, setSystemReduced] = useState(false);
  useEffect(() => {
    const dark = matchMedia('(prefers-color-scheme: dark)'); const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    setSystemDark(dark.matches); setSystemReduced(reduced.matches);
    try { const t = localStorage.getItem('momentum-theme'); const m = localStorage.getItem('momentum-motion'); if (['dark','light','system'].includes(t || '')) updateTheme(t as Theme); if (['full','reduced','system'].includes(m || '')) updateMotion(m as Motion); } catch {}
    const onDark = () => setSystemDark(dark.matches); const onReduced = () => setSystemReduced(reduced.matches);
    dark.addEventListener('change', onDark); reduced.addEventListener('change', onReduced);
    return () => { dark.removeEventListener('change', onDark); reduced.removeEventListener('change', onReduced); };
  }, []);
  const resolvedTheme = theme === 'system' ? (systemDark ? 'dark' : 'light') : theme;
  const reduced = motion === 'reduced' || (motion === 'system' && systemReduced);
  useEffect(() => { document.documentElement.dataset.theme = resolvedTheme; document.documentElement.style.colorScheme = resolvedTheme; }, [resolvedTheme]);
  useEffect(() => { document.documentElement.dataset.motion = reduced ? 'reduced' : 'full'; }, [reduced]);
  const setTheme = useCallback((value: Theme) => { updateTheme(value); try { localStorage.setItem('momentum-theme', value); } catch {} }, []);
  const setMotion = useCallback((value: Motion) => { updateMotion(value); try { localStorage.setItem('momentum-motion', value); } catch {} }, []);
  const syncUser = useCallback((user: User) => { if (!user.is_demo) { setTheme(user.theme as Theme); setMotion(user.motion as Motion); } }, [setTheme, setMotion]);
  return <PreferencesContext.Provider value={{ theme, resolvedTheme, setTheme, motion, reduced, setMotion, syncUser }}><MotionConfig reducedMotion={reduced ? 'always' : 'user'}>{children}</MotionConfig></PreferencesContext.Provider>;
}
export function usePreferences() { const value = useContext(PreferencesContext); if (!value) throw new Error('PreferencesProvider missing'); return value; }

type Toast = { id: number; message: string; tone: 'success' | 'error' | 'info' };
const ToastContext = createContext<(message: string, tone?: Toast['tone']) => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toast = useCallback((message: string, tone: Toast['tone'] = 'success') => { const id = Date.now()+Math.random(); setToasts(items => [...items.slice(-3), { id, message, tone }]); setTimeout(() => setToasts(items => items.filter(item => item.id !== id)), 5500); }, []);
  return <ToastContext.Provider value={toast}>{children}<div className="toast-stack" aria-live="polite">{toasts.map(item => <div key={item.id} className={`toast toast-${item.tone}`}>{item.tone === 'success' ? <Check size={17}/> : item.tone === 'error' ? <AlertCircle size={17}/> : <Info size={17}/>}<span>{item.message}</span><button aria-label="Dismiss notification" onClick={() => setToasts(items => items.filter(t => t.id !== item.id))}><X size={15}/></button></div>)}</div></ToastContext.Provider>;
}
export const useToast = () => useContext(ToastContext);

const WorkspaceContext = createContext<{ user: User; capabilities: Capabilities | null; refreshUser: () => Promise<void> } | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null); const [capabilities, setCapabilities] = useState<Capabilities | null>(null); const [error, setError] = useState('');
  const { syncUser } = usePreferences();
  const refreshUser = useCallback(async () => { const data = await api<{ user: User }>('/auth/me'); setUser(data.user); syncUser(data.user); }, [syncUser]);
  useEffect(() => { refreshUser().catch(e => setError(e.message)); api<{ capabilities: Capabilities }>('/config').then(data => setCapabilities(data.capabilities)).catch(() => {}); }, [refreshUser]);
  if (error) return <div className="auth-loading"><div className="brand-mark large">M</div><h2>Let’s get you back in.</h2><p>{error}</p><a className="button primary" href="/login">Sign in</a><a className="text-link" href="/">Back to home</a></div>;
  if (!user) return <div className="auth-loading"><div className="loading-orbit"/><span>Opening your workspace…</span></div>;
  return <WorkspaceContext.Provider value={{ user, capabilities, refreshUser }}>{children}</WorkspaceContext.Provider>;
}
export function useWorkspace() { const value = useContext(WorkspaceContext); if (!value) throw new Error('WorkspaceProvider missing'); return value; }
export async function savePreferences(data: Record<string, unknown>) { return patch<User>('/auth/preferences', data); }
