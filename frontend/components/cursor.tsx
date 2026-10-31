'use client';
import { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring } from 'motion/react';
import { usePreferences } from './providers';

export function ContextCursor() {
  const { reduced } = usePreferences(); const [enabled, setEnabled] = useState(false); const [visible, setVisible] = useState(false); const [label, setLabel] = useState('');
  const x = useMotionValue(-100), y = useMotionValue(-100); const sx = useSpring(x, { stiffness: 500, damping: 38 }), sy = useSpring(y, { stiffness: 500, damping: 38 });
  useEffect(() => {
    const media = matchMedia('(pointer: fine)'); setEnabled(media.matches && !reduced);
    if (!media.matches || reduced) return;
    const move = (event: PointerEvent) => { x.set(event.clientX); y.set(event.clientY); setVisible(true); const target = (event.target as HTMLElement).closest<HTMLElement>('[data-cursor]'); setLabel(target?.dataset.cursor || ''); };
    const leave = () => setVisible(false);
    window.addEventListener('pointermove', move); document.documentElement.addEventListener('pointerleave', leave);
    return () => { window.removeEventListener('pointermove', move); document.documentElement.removeEventListener('pointerleave', leave); };
  }, [reduced, x, y]);
  if (!enabled) return null;
  return <motion.div aria-hidden="true" className={`context-cursor ${label ? 'has-label' : ''}`} style={{ x: sx, y: sy, opacity: visible && label ? 1 : 0 }} animate={{ width: label ? 72 : 24, height: label ? 72 : 24 }}>{label}</motion.div>;
}
