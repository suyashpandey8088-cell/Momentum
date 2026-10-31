import type { Metadata, Viewport } from 'next';
import '@fontsource-variable/inter';
import '@fontsource-variable/manrope';
import '@fontsource/geist-mono/400.css';
import '@/styles/globals.css';
import '@/styles/app.css';
import { PreferencesProvider, ToastProvider } from '@/components/providers';
import { CommandMenu } from '@/components/command-menu';
import { ContextCursor } from '@/components/cursor';
import { PageTransition } from '@/components/page-transition';

export const metadata: Metadata = { title: { default: 'MOMENTUM — From conversation to completion.', template: '%s · MOMENTUM' }, description: 'Your meetings have a life beyond the meeting. Turn conversations into decisions, decisions into action, and action into measurable progress.', applicationName: 'MOMENTUM', robots: { index: true, follow: true } };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#08090C' };
const themeScript = `(function(){try{var t=localStorage.getItem('momentum-theme');var d=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.dataset.theme=d?'dark':'light';document.documentElement.style.colorScheme=d?'dark':'light';var m=localStorage.getItem('momentum-motion');document.documentElement.dataset.motion=m==='reduced'||(m!=='full'&&matchMedia('(prefers-reduced-motion: reduce)').matches)?'reduced':'full';}catch(e){}})();`;
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" data-theme="dark" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: themeScript }}/></head><body><PreferencesProvider><ToastProvider><PageTransition>{children}</PageTransition><CommandMenu/><ContextCursor/></ToastProvider></PreferencesProvider></body></html>;
}
