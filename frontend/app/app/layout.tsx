import type { Metadata } from 'next';
import { AppShell } from '@/components/app-shell';
export const metadata: Metadata = { title: { default: 'Your workspace', template: '%s · MOMENTUM' }, robots: { index: false, follow: false } };
export default function ApplicationLayout({ children }: { children: React.ReactNode }) { return <AppShell>{children}</AppShell>; }
