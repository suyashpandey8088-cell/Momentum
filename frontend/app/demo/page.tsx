'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle } from 'lucide-react';
import { Logo, Button } from '@/components/ui';
import { post } from '@/lib/api';
export default function DemoEntry(){const [error,setError]=useState('');const [attempt,setAttempt]=useState(0);const started=useRef(false);const router=useRouter();useEffect(()=>{if(started.current&&attempt===0)return;started.current=true;setError('');post<{next:string}>('/auth/demo').then(()=>{router.replace('/app');router.refresh();}).catch(e=>setError(e.message));},[router,attempt]);return <main className="demo-entry"><Logo/><span className={error?'':'loading-orbit'} style={!error?{width:45,height:45}:undefined}/><h1>{error?'A small pause in the momentum.':'A little context. A lot of possibility.'}</h1><p>{error?'We couldn’t open the sample workspace. The API may still be starting.':'Opening your private sample workspace. Real interactions, fictional conversations, and a clear path from words to work.'}</p>{error&&<><div className="form-error"><AlertCircle size={16}/>{error}</div><Button onClick={()=>setAttempt(n=>n+1)}>Try again</Button><Button href="/"variant="ghost">Back to the story</Button></>}<span className="demo-entry-note">No account needed. No external actions. Your sandbox is isolated.</span></main>;}
