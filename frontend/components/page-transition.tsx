'use client';
import { usePathname } from 'next/navigation';
import { AnimatePresence, motion } from 'motion/react';
import type { ReactNode } from 'react';
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (pathname.startsWith('/app')) return children;
  return <AnimatePresence mode="wait" initial={false}><motion.div key={pathname} className="page-transition" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.22 }}>{children}</motion.div></AnimatePresence>;
}
