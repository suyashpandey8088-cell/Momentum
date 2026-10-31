import asyncio
import logging
from datetime import timedelta
from sqlalchemy import select, update
from core.database import session_scope, engine
from core.config import get_settings
from models.entities import *
from agents.pipeline import process_meeting, ConfigurationRequired
from agents.memory import embed_memories
from services.common import notify, audit, utc
from services.storage import delete_recording

logger = logging.getLogger('momentum.worker')

def claim_job():
    with session_scope() as db:
        stale = now()-timedelta(minutes=20)
        for job in db.scalars(select(Job).where(Job.status == 'processing', Job.locked_at < stale)):
            job.status = 'failed' if job.attempts >= 3 else 'queued'; job.error = 'Worker interrupted; safely reclaiming job.'
        query = select(Job).where(Job.status == 'queued', Job.run_after <= now()).order_by(Job.created_at).limit(1)
        if engine.dialect.name == 'postgresql': query = query.with_for_update(skip_locked=True)
        job = db.scalar(query)
        if not job: return None
        result = db.execute(update(Job).where(Job.id == job.id, Job.status == 'queued').values(status='processing', locked_at=now(), attempts=Job.attempts+1))
        return job.id if result.rowcount else None

def run_job(job_id: str):
    with session_scope() as db:
        job = db.get(Job, job_id)
        if not job or job.status != 'processing': return
        try:
            meeting = db.get(Meeting, job.meeting_id) if job.meeting_id else None
            if not meeting: raise ValueError('The meeting was deleted before processing.')
            process_meeting(db, meeting)
            job.status = 'completed'; job.error = ''
        except ConfigurationRequired as error:
            job.status = 'failed'; job.error = str(error)
            meeting = db.get(Meeting, job.meeting_id)
            if meeting: meeting.status = 'needs_configuration'; meeting.processing_error = str(error)
        except Exception as error:
            logger.exception('Meeting processing failed')
            db.rollback(); job = db.get(Job, job_id)
            job.error = 'Processing failed. Check the provider configuration or retry with a valid recording/transcript.'
            job.status = 'queued' if job.attempts < 3 else 'failed'
            job.run_after = now()+timedelta(seconds=30*job.attempts)
            meeting = db.get(Meeting, job.meeting_id) if job.meeting_id else None
            if meeting:
                meeting.status = 'failed' if job.status == 'failed' else 'queued'
                meeting.processing_error = job.error
        db.commit()

def follow_up():
    with session_scope() as db:
        tomorrow = now()+timedelta(days=2)
        for org in db.scalars(select(Organization)):
            users = list(db.scalars(select(User).join(Membership, Membership.user_id == User.id).where(Membership.organization_id == org.id)))
            tasks = list(db.scalars(select(Task).where(Task.organization_id == org.id, Task.status != 'completed', Task.approval_status == 'approved', Task.deadline != None)))
            for task in tasks:
                deadline = utc(task.deadline)
                is_overdue = deadline < now()
                upcoming = now() <= deadline <= tomorrow
                if not is_overdue and not upcoming: continue
                category = 'overdue' if is_overdue else 'deadlines'
                for user in users:
                    prefs = user.notification_preferences
                    if not prefs.get(category, True): continue
                    days = max(0, prefs.get('reminder_days', 2))
                    if upcoming and deadline > now()+timedelta(days=days): continue
                    notify(db, org.id, user.id, category, 'A commitment needs attention' if is_overdue else 'A deadline is coming up', f'{task.title} · due {deadline.strftime("%b %d")}', '/app/tasks', f'{category}:{task.id}:{now().date()}')
            if now().weekday() == 0:
                for user in users:
                    if user.notification_preferences.get('weekly', True):
                        done = sum(t.status == 'completed' for t in tasks)
                        notify(db, org.id, user.id, 'weekly', 'Your weekly execution briefing', f'{len(tasks)} open commitments. Review progress and agree on the next steps.', '/app/reports', f'weekly:{now().isocalendar().year}:{now().isocalendar().week}')
            cutoff = now()-timedelta(days=org.retention_days)
            for meeting in db.scalars(select(Meeting).where(Meeting.organization_id == org.id, Meeting.created_at < cutoff, Meeting.storage_key != '')):
                delete_recording(meeting.storage_key)
                meeting.storage_key = ''; meeting.file_size = 0
                audit(db, org.id, None, 'Recording removed by retention policy', 'meeting', meeting.id)
            try: embed_memories(db, org.id)
            except Exception: logger.warning('Background embedding update skipped for this workspace.')
        db.commit()

def tick():
    job_id = claim_job()
    if job_id: run_job(job_id)
    return bool(job_id)

async def worker_loop():
    last_maintenance = 0
    redis_client = None
    if get_settings().redis_url:
        try:
            import redis.asyncio as redis
            redis_client = redis.from_url(get_settings().redis_url)
            await redis_client.ping()
        except Exception:
            logger.warning('Redis unavailable; using database job coordination.')
            redis_client = None
    while True:
        try:
            worked = await asyncio.to_thread(tick)
            if asyncio.get_event_loop().time() - last_maintenance > 60:
                lock = await redis_client.set('momentum:maintenance', '1', nx=True, ex=55) if redis_client else True
                if lock: await asyncio.to_thread(follow_up)
                last_maintenance = asyncio.get_event_loop().time()
            await asyncio.sleep(0.5 if worked else 2)
        except asyncio.CancelledError:
            if redis_client: await redis_client.aclose()
            raise
        except Exception:
            logger.exception('Worker loop error')
            await asyncio.sleep(5)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())
