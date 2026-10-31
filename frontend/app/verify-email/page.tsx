import { Suspense } from 'react';
import { AuthForm } from '@/components/auth-form';
export const metadata = { title: 'Verify', robots: { index: false } };
export default function Page() { return <Suspense fallback={<div className="auth-loading"><span className="loading-orbit"/></div>}><AuthForm mode="verify"/></Suspense>; }
