import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { Task } from '@/types';
export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
export const initials = (name: string) => name.split(' ').map(part => part[0]).slice(0, 2).join('').toUpperCase();
export const formatDate = (date: string | null | undefined, options?: Intl.DateTimeFormatOptions) => date ? new Date(date).toLocaleDateString('en-US', options || { month: 'short', day: 'numeric' }) : 'No deadline';
export const formatTime = (seconds: number | null) => seconds === null ? '—' : `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
export const statusLabel = (status: string) => ({ pending: 'Pending', in_progress: 'In progress', blocked: 'Blocked', completed: 'Completed', overdue: 'Overdue', needs_configuration: 'Setup needed', ready: 'Ready', queued: 'Queued', processing: 'Processing', uploaded: 'Uploaded', failed: 'Needs attention', proposed: 'Proposed', reviewed: 'Reviewed', approved: 'Approved', executed: 'Executed', verified: 'Verified' }[status] || status.replaceAll('_', ' '));
export function relativeTime(date: string) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(date).getTime()) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
  if (minutes < 10080) return `${Math.floor(minutes / 1440)}d ago`;
  return formatDate(date);
}
export function downloadFile(content: BlobPart, filename: string, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const actionLabels: Record<string, string> = { local_task: 'Create a task', gmail_draft: 'Draft a follow-up', calendar_event: 'Create a calendar event', linear_issue: 'Create a Linear issue', notion_page: 'Create a Notion page', slack_message: 'Send a Slack update' };
export const actionProviders: Record<string, string> = { gmail_draft: 'gmail', calendar_event: 'google_calendar', linear_issue: 'linear', notion_page: 'notion', slack_message: 'slack' };
export const priorityOrder: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 };
export function sortTasks(tasks: Task[], sort: string) { return [...tasks].sort((a, b) => sort === 'priority' ? priorityOrder[a.priority] - priorityOrder[b.priority] : (a.deadline || '9999').localeCompare(b.deadline || '9999')); }
