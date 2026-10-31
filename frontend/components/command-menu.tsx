'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LayoutDashboard, AudioLines, CheckCheck, Folder, Brain, Plug, ChartNoAxesCombined, Settings, Sun, Moon, Sparkles, ArrowUpRight, Command, Home } from 'lucide-react';
import { Modal } from './ui';
import { usePreferences, useToast } from './providers';

export function CommandMenu() {
  const [open, setOpen] = useState(false); const [query, setQuery] = useState(''); const [active, setActive] = useState(0);
  const router = useRouter(); const { resolvedTheme, setTheme, reduced, setMotion } = usePreferences(); const toast = useToast();
  useEffect(() => {
    let sequence = '';
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setOpen(value => !value); setQuery(''); setActive(0); }
      const target = event.target as HTMLElement;
      if (target.closest('input,textarea,select,[contenteditable]') || event.metaKey || event.ctrlKey) return;
      sequence = (sequence + event.key.toLowerCase()).slice(-8);
      if (sequence === 'momentum') { toast('You found the loop. Conversations → decisions → done. Keep going.', 'info'); document.dispatchEvent(new Event('momentum:celebrate')); sequence = ''; }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener('keydown', handler); window.addEventListener('momentum:command', onOpen);
    return () => { window.removeEventListener('keydown', handler); window.removeEventListener('momentum:command', onOpen); };
  }, [toast]);
  const commands = [
    { label: 'Overview', detail: 'Your execution at a glance', icon: LayoutDashboard, action: () => router.push('/app') },
    { label: 'Meetings', detail: 'Conversations worth following through', icon: AudioLines, action: () => router.push('/app/meetings') },
    { label: 'Tasks & approvals', detail: 'Turn commitments into completion', icon: CheckCheck, action: () => router.push('/app/tasks') },
    { label: 'Projects', detail: 'The bigger picture', icon: Folder, action: () => router.push('/app/projects') },
    { label: 'AI Memory', detail: 'Ask your workspace what happened', icon: Brain, action: () => router.push('/app/memory') },
    { label: 'Integrations', detail: 'Connect your execution stack', icon: Plug, action: () => router.push('/app/integrations') },
    { label: 'Reports', detail: 'Progress, without the status meeting', icon: ChartNoAxesCombined, action: () => router.push('/app/reports') },
    { label: 'Settings', detail: 'Make MOMENTUM yours', icon: Settings, action: () => router.push('/app/settings') },
    { label: 'Back to the story', detail: 'MOMENTUM homepage', icon: Home, action: () => router.push('/') },
    { label: `Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`, detail: 'Appearance', icon: resolvedTheme === 'dark' ? Sun : Moon, action: () => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark') },
    { label: `Use ${reduced ? 'full' : 'reduced'} motion`, detail: 'Accessibility preference', icon: Sparkles, action: () => setMotion(reduced ? 'full' : 'reduced') },
  ].filter(item => `${item.label} ${item.detail}`.toLowerCase().includes(query.toLowerCase()));
  const run = (index: number) => { commands[index]?.action(); setOpen(false); };
  return <Modal open={open} onClose={() => setOpen(false)} title="A little shortcut to your next move." description="Go anywhere. Change a preference. Keep moving."><div className="command-input"><Command size={19}/><input autoFocus placeholder="Where would you like to go?" value={query} onChange={e => { setQuery(e.target.value); setActive(0); }} onKeyDown={e => { if (e.key === 'ArrowDown') { e.preventDefault(); setActive(i => Math.min(i+1, commands.length-1)); } if (e.key === 'ArrowUp') { e.preventDefault(); setActive(i => Math.max(i-1, 0)); } if (e.key === 'Enter') run(active); }} aria-label="Search commands"/></div><div className="command-list">{commands.map((item, index) => <button key={item.label} className={active === index ? 'active' : ''} onMouseEnter={() => setActive(index)} onClick={() => run(index)}><item.icon size={19}/><span><strong>{item.label}</strong><small>{item.detail}</small></span><ArrowUpRight size={16}/></button>)}{!commands.length && <p className="command-empty">No matching commands. Try “tasks” or “theme”.</p>}</div><div className="command-footer"><span><kbd>↑</kbd><kbd>↓</kbd> to navigate</span><span><kbd>↵</kbd> to open</span><span><kbd>esc</kbd> to close</span></div></Modal>;
}
