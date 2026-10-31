import logging
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from models.entities import *
from schemas.contracts import MeetingIntelligence, ExtractedTask
from agents.intelligence import extract_rule_based, tokenize
from agents.memory import retrieve, embed_memories
from services.providers import reasoning_provider, transcription_provider
from services.common import audit, notify, utc
from services.storage import recording_path
from core.config import get_settings

logger = logging.getLogger('momentum.pipeline')

class ConfigurationRequired(Exception): pass

def transcribe_audio(meeting: Meeting, db: Session):
    provider = transcription_provider()
    if not provider: raise ConfigurationRequired('Recording saved privately. Configure a speech-to-text provider to transcribe audio, or import the transcript to continue with grounded local extraction.')
    from services.object_storage import download, configured
    with tempfile.TemporaryDirectory(prefix='momentum-') as directory:
        source = Path(directory) / meeting.filename
        if configured(): download(meeting.storage_key, str(source))
        else: source = recording_path(meeting.storage_key)
        audio_path = source
        if source.suffix.lower() in {'.mp4', '.m4a', '.webm'}:
            import imageio_ffmpeg
            audio_path = Path(directory) / 'audio.wav'
            result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(source), '-vn', '-ac', '1', '-ar', '16000', str(audio_path)], capture_output=True, timeout=300)
            if result.returncode: raise ValueError('The recording could not be decoded. Check that the file contains a valid audio track.')
        segments = provider.transcribe(str(audio_path), audio_path.name)
    for sequence, segment in enumerate(segments): db.add(TranscriptSegment(meeting_id=meeting.id, sequence=sequence, **segment.model_dump()))
    db.flush()
    return provider.name

def resolve_dependencies(db: Session, candidates: list[ExtractedTask], tasks: list[Task]):
    for index, (candidate, task) in enumerate(zip(candidates, tasks)):
        for dependency in candidate.dependencies:
            words = tokenize(dependency)
            matches = [(other, len(words & tokenize(other.title))) for other in candidates[:index]]
            matches = [(other, score) for other, score in matches if score >= max(1, min(2, len(words)))]
            matches.sort(key=lambda entry: entry[1], reverse=True)
            if matches and (len(matches) == 1 or matches[0][1] > matches[1][1]):
                other_task = tasks[candidates.index(matches[0][0])]
                if not db.get(TaskDependency, (task.id, other_task.id)): db.add(TaskDependency(task_id=task.id, depends_on_id=other_task.id))
            elif dependency not in task.description:
                task.description += f'\nUnconfirmed dependency: {dependency}.'

def process_meeting(db: Session, meeting: Meeting):
    org_id = meeting.organization_id
    meeting.status = 'processing'; meeting.processing_error = ''; db.commit()
    segments = list(db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting.id).order_by(TranscriptSegment.sequence)))
    speech_name = None
    if not segments:
        speech_name = transcribe_audio(meeting, db)
        segments = list(db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting.id).order_by(TranscriptSegment.sequence)))
    people = list(db.scalars(select(Participant).join(MeetingParticipant, MeetingParticipant.participant_id == Participant.id).where(MeetingParticipant.meeting_id == meeting.id)))
    for segment in segments:
        name = segment.speaker.strip()
        if name and name != 'Unknown speaker' and not re.match(r'^(speaker[\s_-]?\d+|unknown.*)$', name, re.I) and not any(p.name.casefold() == name.casefold() for p in people):
            person = Participant(organization_id=org_id, name=name, role='Identified from transcript')
            db.add(person); db.flush(); people.append(person); db.add(MeetingParticipant(meeting_id=meeting.id, participant_id=person.id))
    db.flush()
    historical = retrieve(db, org_id, ' '.join(s.text for s in segments)[:2000], meeting.project_id, 4)
    context = '\n'.join(memory.content for memory, score in historical)
    provider = reasoning_provider()
    warning = ''
    if provider:
        try: result = provider.analyze(segments, [p.name for p in people], utc(meeting.occurred_at).isoformat(), context)
        except Exception as error:
            logger.warning('Reasoning provider failed; using grounded rules: %s', type(error).__name__)
            warning = 'The configured reasoning provider failed validation or was unavailable. Grounded local rules were used instead.'
            result = extract_rule_based(segments, [p.name for p in people], utc(meeting.occurred_at))
            provider = None
    else: result = extract_rule_based(segments, [p.name for p in people], utc(meeting.occurred_at))
    # A re-run replaces only unapproved, untouched extraction drafts. Approved work is never overwritten.
    old_tasks = list(db.scalars(select(Task).where(Task.organization_id == org_id, Task.meeting_id == meeting.id, Task.approval_status == 'pending')))
    for task in old_tasks:
        if db.scalar(select(TaskComment.id).where(TaskComment.task_id == task.id)): continue
        for action in db.scalars(select(ExecutionAction).where(ExecutionAction.organization_id == org_id, ExecutionAction.task_id == task.id, ExecutionAction.status.in_(['proposed', 'reviewed']))): db.delete(action)
        db.execute(delete(TaskDependency).where((TaskDependency.task_id == task.id) | (TaskDependency.depends_on_id == task.id)))
        db.delete(task)
    db.execute(delete(Decision).where(Decision.organization_id == org_id, Decision.meeting_id == meeting.id))
    db.execute(delete(Memory).where(Memory.organization_id == org_id, Memory.meeting_id == meeting.id))
    meeting.summary = result.summary; meeting.topics = result.topics; meeting.questions = result.questions; meeting.risks = result.risks; meeting.next_steps = result.next_steps
    meeting.provider = (provider.name if provider else 'Grounded local rules · no LLM configured') + (f' + {speech_name}' if speech_name else '')
    meeting.processing_error = warning
    for decision in result.decisions: db.add(Decision(organization_id=org_id, meeting_id=meeting.id, **decision.model_dump()))
    tasks, candidates = [], []
    names = {p.name.casefold(): p for p in people}
    for candidate in result.tasks:
        owner = names.get(candidate.assignee.casefold()) if candidate.assignee else None
        deadline = None
        if candidate.deadline:
            try: deadline = datetime.fromisoformat(candidate.deadline.replace('Z', '+00:00'))
            except ValueError: pass
        confidence = min(candidate.confidence, 0.8 if not owner or not deadline else 1.0)
        task = Task(organization_id=org_id, project_id=meeting.project_id, meeting_id=meeting.id, title=candidate.title, description=candidate.description, assignee_id=owner.id if owner else None, deadline=deadline, priority=candidate.priority, status='pending', approval_status='pending', source_segment_ids=candidate.source_segment_ids, confidence=confidence, created_by=meeting.created_by)
        db.add(task); db.flush(); tasks.append(task); candidates.append(candidate)
        db.add(ExecutionAction(organization_id=org_id, meeting_id=meeting.id, task_id=task.id, kind='local_task', status='proposed', payload={'title': task.title}, source_context=' '.join(s.text for s in segments if s.id in candidate.source_segment_ids)))
    resolve_dependencies(db, candidates, tasks)
    db.add(Memory(organization_id=org_id, project_id=meeting.project_id, meeting_id=meeting.id, kind='summary', content=f'{meeting.title}: {meeting.summary}', source_label=meeting.title))
    for decision in result.decisions: db.add(Memory(organization_id=org_id, project_id=meeting.project_id, meeting_id=meeting.id, kind='decision', content=decision.text, source_label=meeting.title))
    for task in tasks: db.add(Memory(organization_id=org_id, project_id=meeting.project_id, meeting_id=meeting.id, task_id=task.id, kind='commitment', content=f'{task.title}. {task.description}', source_label=meeting.title))
    db.flush()
    try: embed_memories(db, org_id)
    except Exception: logger.warning('Embeddings unavailable; keeping lexical memory.')
    meeting.status = 'ready'
    if meeting.created_by:
        user = db.get(User, meeting.created_by)
        if user and user.notification_preferences.get('processing', True): notify(db, org_id, user.id, 'processing', 'Your meeting is ready', f'{meeting.title}: {len(tasks)} commitments are ready for review.', f'/app/meetings/{meeting.id}', f'processing:{meeting.id}:{now().timestamp()}')
    audit(db, org_id, meeting.created_by, 'Meeting intelligence is ready', 'meeting', meeting.id, {'tasks': len(tasks), 'decisions': len(result.decisions), 'provider': meeting.provider})
    db.commit()
