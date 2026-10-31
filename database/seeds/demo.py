"""Explicitly fictional sample workspace. No external account is connected."""
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.entities import *

def seed_workspace(db: Session, org: Organization, user: User):
    if db.scalar(select(Project).where(Project.organization_id == org.id)): return
    base = now().replace(hour=10, minute=0, second=0, microsecond=0)
    projects = [
        Project(organization_id=org.id, name='Website launch', description='A clearer story. A faster experience. Our next chapter, live.', color='#5B7CFF'),
        Project(organization_id=org.id, name='Mobile experience', description='Make the first five minutes feel effortless.', color='#63D9E8'),
        Project(organization_id=org.id, name='Q4 planning', description='The priorities that move us forward.', color='#D6AE71'),
    ]
    db.add_all(projects); db.flush()
    people = [
        Participant(organization_id=org.id, name='Maya Chen', email='maya@example.com', role='Product lead', color='#5B7CFF'),
        Participant(organization_id=org.id, name='Rahul Sharma', email='rahul@example.com', role='Frontend engineer', color='#63D9E8'),
        Participant(organization_id=org.id, name='Priya Kapoor', email='priya@example.com', role='Content designer', color='#C69CE8'),
        Participant(organization_id=org.id, name='Alex Rivera', email='alex@example.com', role='Design engineer', color='#D6AE71'),
    ]
    db.add_all(people); db.flush()
    meeting_specs = [
        ('Website launch · Weekly sync', 0, 0, 32, 'The team aligned on the website launch. Rahul owns the frontend, Priya is preparing the copy, and Alex will run the final accessibility checks. The launch is planned for Friday, with a few open questions about analytics and enterprise pricing.', ['Website launch', 'Ownership', 'Launch readiness'], ['Who will sign off on the enterprise pricing page?', 'Has the analytics consent flow been verified?'], ['Copy approval is a dependency for the final frontend build.']),
        ('Product & design alignment', 1, 1, 45, 'The group reviewed mobile onboarding research. The team decided to reduce the first-run flow to three steps and test the new empty states before implementation. Alex is preparing the prototype.', ['Mobile onboarding', 'Research', 'Prototyping'], ['Which customer segment should join the next test?'], []),
        ('Q4 growth planning', 2, 2, 50, 'Maya shared the Q4 growth priorities. The team agreed to focus on activation before adding new acquisition channels. Priya will collect the customer language needed for the next experiment.', ['Q4 priorities', 'Activation', 'Experiments'], [], ['The analytics baseline is not yet validated.']),
        ('Mobile onboarding review', 4, 1, 28, 'The team reviewed the onboarding journey and identified friction in workspace setup. Alex completed the interaction audit. A simplified flow is now in progress.', ['Onboarding', 'Usability'], ['Do we need a separate flow for invited teammates?'], []),
        ('Website launch · Kickoff', 7, 0, 40, 'The website redesign kicked off. The team decided to keep the existing navigation structure and prioritize a fast, accessible homepage. Rahul committed to the first frontend build, while Priya owns the messaging. The original copy deadline was missed and remains an open commitment.', ['Website redesign', 'Information architecture', 'Accessibility'], ['Which customer proof points can we publish?'], ['The copy deadline from kickoff needs to be recovered.']),
        ('Customer feedback debrief', 9, 2, 35, 'Customer interviews highlighted the need for clearer onboarding and better follow-through after meetings. The team selected three themes for the Q4 roadmap and archived the completed research synthesis.', ['Customer research', 'Roadmap'], [], []),
    ]
    meetings = []
    for index, (title, days, project_idx, duration, summary, topics, questions, risks) in enumerate(meeting_specs):
        meeting = Meeting(organization_id=org.id, project_id=projects[project_idx].id, title=title, occurred_at=base - timedelta(days=days), duration_minutes=duration, status='ready', source='transcript', summary=summary, topics=topics, questions=questions, risks=risks, next_steps=['Review the proposed action items.', 'Confirm owners and deadlines before execution.'], provider='Sample data · not AI-generated', consent=True, created_by=user.id, created_at=base-timedelta(days=days))
        db.add(meeting); db.flush(); meetings.append(meeting)
        for person in people:
            db.add(MeetingParticipant(meeting_id=meeting.id, participant_id=person.id))
        lines = [
            ('Maya Chen', 'Let’s keep this focused on what we need to ship. Where are we with the website launch?'),
            ('Rahul Sharma', 'The frontend is coming together. I’ll finish the landing page by Friday.'),
            ('Priya Kapoor', 'I’ll prepare the website copy by Wednesday so Rahul has time to integrate it.'),
            ('Maya Chen', 'We decided to keep the existing navigation for this release. Let’s prioritize an accessible, fast homepage.'),
            ('Alex Rivera', 'I can run the accessibility checks on Thursday. The frontend needs to be ready first.'),
            ('Maya Chen', 'One open question: who is signing off on enterprise pricing? We should confirm that before launch.'),
        ] if index == 0 else [(people[(i + index) % 4].name, sentence) for i, sentence in enumerate([summary, 'We decided to document the next steps and check progress at our next sync.', 'What still needs confirmation before we move ahead?'])]
        segments = []
        for seq, (speaker, text) in enumerate(lines):
            segment = TranscriptSegment(meeting_id=meeting.id, sequence=seq, speaker=speaker, start_seconds=seq*65 if index == 0 else None, end_seconds=(seq+1)*65 if index == 0 else None, text=text)
            db.add(segment); segments.append(segment)
        db.flush()
        decision_text = 'Keep the existing navigation and prioritize an accessible, fast homepage.' if index == 0 else next((s.text for s in segments if 'decided' in s.text), 'Document the next steps and review progress at the next sync.')
        source = next((s for s in segments if 'decided' in s.text), segments[0])
        db.add(Decision(organization_id=org.id, meeting_id=meeting.id, text=decision_text, source_segment_ids=[source.id], confidence=0.98))
        db.add(Memory(organization_id=org.id, project_id=meeting.project_id, meeting_id=meeting.id, kind='summary', content=f'{title}: {summary}', source_label=title))
    task_specs = [
        ('Complete the landing page', 0, 1, 5, 'high', 'in_progress', 'Build the responsive landing page and integrate approved website copy.', 0),
        ('Prepare website copy', 0, 2, 3, 'high', 'in_progress', 'Finalize the homepage messaging, product proof points, and calls to action.', 0),
        ('Run accessibility checks', 0, 3, 4, 'high', 'pending', 'Audit keyboard navigation, color contrast, and screen-reader behavior.', 0),
        ('Verify analytics consent', 0, None, 6, 'medium', 'pending', 'Confirm consent before enabling production analytics.', 0),
        ('Prototype the new onboarding', 1, 3, 2, 'high', 'in_progress', 'Three-step onboarding with a useful empty state.', 1),
        ('Review first-run experience', 1, 0, 7, 'medium', 'pending', 'Review the mobile prototype with the product team.', 1),
        ('Define activation baseline', 2, 0, -1, 'high', 'pending', 'Validate the current activation funnel before the next experiment.', 2),
        ('Collect customer language', 2, 2, 3, 'medium', 'pending', 'Pull the strongest phrases from recent customer interviews.', 2),
        ('Complete interaction audit', 1, 3, -1, 'medium', 'completed', 'Document friction across the mobile onboarding journey.', 3),
        ('Build the component foundation', 0, 1, -2, 'high', 'completed', 'Ship the shared tokens, controls, and responsive layouts.', 4),
        ('Map the information architecture', 0, 0, -3, 'medium', 'completed', 'Agree on navigation and page hierarchy.', 4),
        ('Synthesize customer interviews', 2, 2, -4, 'medium', 'completed', 'Share the three strongest themes with the team.', 5),
        ('Set up preview environment', 0, 1, -2, 'medium', 'completed', 'Create a reviewable deployment for the team.', 4),
        ('Draft launch announcement', 0, 2, 6, 'low', 'pending', 'Prepare the launch note for existing customers.', 0),
        ('Test mobile breakpoints', 1, 3, -2, 'high', 'blocked', 'Waiting for the final onboarding prototype.', 1),
        ('Document Q4 priorities', 2, 0, -3, 'medium', 'completed', 'Publish the agreed activation-first roadmap.', 2),
        ('Review launch checklist', 0, 0, 5, 'high', 'pending', 'Confirm every launch dependency has a clear owner.', 0),
        ('Archive research notes', 2, 2, -5, 'low', 'completed', 'Organize the source interviews and synthesis.', 5),
    ]
    tasks = []
    for index, (title, p, owner, due, priority, status, description, meeting_idx) in enumerate(task_specs):
        meeting = meetings[meeting_idx]
        segments = list(db.scalars(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting.id).order_by(TranscriptSegment.sequence)))
        task = Task(organization_id=org.id, project_id=projects[p].id, meeting_id=meeting.id, title=title, description=description, assignee_id=people[owner].id if owner is not None else None, deadline=base.replace(hour=17) + timedelta(days=due), priority=priority, status=status, confidence=0.96 if owner is not None else 0.65, approval_status='approved', source_segment_ids=[segments[[1,2,4,5][index] if meeting_idx == 0 and index < 4 else 0].id], created_by=user.id, created_at=meeting.occurred_at, completed_at=base+timedelta(days=due) if status == 'completed' else None)
        db.add(task); tasks.append(task)
    db.flush()
    db.add(TaskDependency(task_id=tasks[0].id, depends_on_id=tasks[1].id))
    db.add(TaskDependency(task_id=tasks[2].id, depends_on_id=tasks[0].id))
    db.add(TaskDependency(task_id=tasks[14].id, depends_on_id=tasks[4].id))
    extracted = Task(organization_id=org.id, project_id=projects[0].id, meeting_id=meetings[0].id, title='Confirm enterprise pricing sign-off', description='An owner was not named in the meeting. Confirm who is responsible before assigning this task.', assignee_id=None, deadline=None, priority='medium', status='pending', approval_status='pending', confidence=0.7, source_segment_ids=[db.scalar(select(TranscriptSegment.id).where(TranscriptSegment.meeting_id == meetings[0].id).order_by(TranscriptSegment.sequence.desc()).limit(1))], created_by=user.id)
    db.add(extracted); db.flush()
    db.add(ExecutionAction(organization_id=org.id, meeting_id=meetings[0].id, task_id=extracted.id, kind='local_task', status='proposed', payload={'title': extracted.title}, source_context='One open question: who is signing off on enterprise pricing? We should confirm that before launch.', idempotency_key=f'seed-local-{org.id}'))
    db.add(ExecutionAction(organization_id=org.id, meeting_id=meetings[0].id, task_id=tasks[0].id, kind='gmail_draft', status='proposed', payload={'to': 'rahul@example.com', 'subject': 'Website launch — your next steps', 'body': 'Hi Rahul,\n\nFollowing our website launch sync, you own the landing page frontend, due Friday. Priya is preparing the copy for Wednesday, and Alex will run accessibility checks afterward.\n\nPlease flag any blockers so we can keep the launch on track.\n\nThanks,\nMaya'}, source_context='I’ll finish the landing page by Friday.', idempotency_key=f'seed-email-{org.id}'))
    db.add(ExecutionAction(organization_id=org.id, meeting_id=meetings[0].id, task_id=tasks[2].id, kind='calendar_event', status='proposed', payload={'title': 'Website accessibility review', 'description': 'Review keyboard navigation, contrast, and screen-reader support before launch.', 'start': (base+timedelta(days=4, hours=4)).isoformat(), 'end': (base+timedelta(days=4, hours=5)).isoformat(), 'attendees': ['alex@example.com']}, source_context='I can run the accessibility checks on Thursday.', idempotency_key=f'seed-calendar-{org.id}'))
    for task in tasks:
        db.add(Memory(organization_id=org.id, project_id=task.project_id, meeting_id=task.meeting_id, task_id=task.id, kind='commitment', content=f'{task.title}. {task.description}', source_label=next(m.title for m in meetings if m.id == task.meeting_id)))
    for i, (action, entity_type, entity_id, days) in enumerate([('Meeting intelligence is ready', 'meeting', meetings[0].id, 0), ('Landing page moved to in progress', 'task', tasks[0].id, 0), ('Interaction audit completed', 'task', tasks[8].id, 1), ('New decision captured', 'meeting', meetings[1].id, 1), ('Component foundation completed', 'task', tasks[9].id, 2)]):
        db.add(AuditLog(organization_id=org.id, user_id=user.id, action=action, entity_type=entity_type, entity_id=entity_id, details={'sample': True}, created_at=base-timedelta(days=days, minutes=i*27)))
    db.add(Notification(organization_id=org.id, user_id=user.id, type='processing', title='Your meeting is ready', body='Website launch · Weekly sync has 3 proposed actions to review.', link=f'/app/meetings/{meetings[0].id}', dedupe_key='sample-ready'))
    db.add(Notification(organization_id=org.id, user_id=user.id, type='overdue', title='One commitment needs attention', body='Define activation baseline is overdue. Review the task to agree on a new deadline.', link='/app/tasks', dedupe_key='sample-overdue'))
    db.flush()
    return meetings[0]
