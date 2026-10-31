'use client';
import { type ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft, Check, AudioLines, GitBranch, ShieldCheck } from 'lucide-react';
import { Logo, ThemeToggle } from './ui';
import { NetworkFallback } from './network-scene';
export function AuthShell({ children, step }: { children: ReactNode; step?: string }) {
  return <div className="auth-shell"><div className="auth-form-side"><div className="auth-top"><Link href="/" aria-label="MOMENTUM home"><Logo/></Link><ThemeToggle/></div><div className="auth-form-container">{children}</div><div className="auth-bottom"><Link href="/"><ArrowLeft size={13}/>Back to the story</Link><span><ShieldCheck size={12}/>Private by design</span></div></div><aside className="auth-story"><div className="auth-story-grid"/><span className="auth-story-kicker">FROM CONVERSATION TO COMPLETION</span><div className="auth-story-visual"><NetworkFallback/><div className="auth-story-note"><span><Check size={14}/></span><div><small>THE CONVERSATION IS JUST THE START.</small><strong>Let’s see it through.</strong></div></div></div><div className="auth-story-copy"><h2>The meeting ends.<br/><span>The work doesn’t have to.</span></h2><p>One connected space for the decisions, commitments,<br/>and small next moves that make a big difference.</p><div className="auth-story-steps"><span><AudioLines size={16}/>Capture the context</span><i/><span><GitBranch size={16}/>Connect the work</span><i/><span><Check size={16}/>Keep it moving</span></div></div><div className="auth-story-footer"><span>MOMENTUM / A BETTER WAY FORWARD</span><span>{step || '01 — THE BEGINNING'}</span></div></aside></div>;
}
