'use client';
import { Logo, Button } from '@/components/ui';
import { AlertCircle } from 'lucide-react';
export default function ErrorPage({reset}:{error:Error&{digest?:string};reset:()=>void}){return <main className="not-found-page"><Logo/><AlertCircle size={35}style={{color:'var(--amber)',marginBottom:25}}/><h1>A small pause. Not a full stop.</h1><p>This view couldn’t be loaded. Your workspace data is still private. Try again, or head back to the overview.</p><div><Button onClick={reset}>Try again</Button><Button href="/app"variant="secondary">Back to overview</Button></div></main>;}
