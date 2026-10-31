import { MeetingWorkspace } from '@/features/meeting-workspace';
export const metadata = { title: 'Meeting intelligence' };
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <MeetingWorkspace id={id}/>;}
