'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
export function useApi<T>(path: string | null, poll?: number) {
  const [data,setData]=useState<T|null>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState('');const mounted=useRef(true);
  const refresh=useCallback(async()=>{if(!path)return;try{const result=await api<T>(path);if(mounted.current){setData(result);setError('');}}catch(e){if(mounted.current)setError(e instanceof Error?e.message:'Please try again.');}finally{if(mounted.current)setLoading(false);}},[path]);
  useEffect(()=>{mounted.current=true;setLoading(true);refresh();return()=>{mounted.current=false;};},[refresh]);
  useEffect(()=>{if(!poll)return;const timer=setInterval(refresh,poll);return()=>clearInterval(timer);},[poll,refresh]);
  return {data,loading,error,refresh,setData};
}
export function useWorkspaceData() {
  const projects=useApi<import('@/types').Project[]>('/projects');const people=useApi<import('@/types').Participant[]>('/participants');
  return {projects:projects.data||[],people:people.data||[],loading:projects.loading||people.loading,error:projects.error||people.error,refresh:()=>{projects.refresh();people.refresh();}};
}
