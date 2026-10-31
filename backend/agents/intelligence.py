"""Grounded extraction fallback. It is intentionally conservative, not an LLM pretend-API."""
import re
from datetime import datetime, timedelta, timezone
from schemas.contracts import MeetingIntelligence, ExtractedTask, DecisionInput, SegmentInput

WEEKDAYS = {name: i for i, name in enumerate(['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'])}
MONTHS = {name.lower(): i for i, name in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'], 1)}
STOPWORDS = set('a an the this that these those we our us i you they it is are was were be been to of for and or in on at by with from as will need should can could would have has had let us please just so then than next'.split())

def normalize_transcript(text: str) -> list[SegmentInput]:
    segments = []
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        timestamp = re.match(r'^\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*', line)
        start = None
        if timestamp:
            a, b, c = timestamp.groups()
            start = int(a)*60 + int(b) if c is None else int(a)*3600 + int(b)*60 + int(c)
            line = line[timestamp.end():]
        speaker_match = re.match(r'^([^:]{1,80}):\s*(.+)$', line)
        speaker, content = speaker_match.groups() if speaker_match else ('Unknown speaker', line)
        segments.append(SegmentInput(speaker=speaker.strip(), text=content.strip(), start_seconds=start))
    return segments

def resolve_deadline(text: str, reference: datetime) -> str | None:
    if reference.tzinfo is None: reference = reference.replace(tzinfo=timezone.utc)
    lower = text.lower()
    date = None
    if 'tomorrow' in lower: date = reference.date() + timedelta(days=1)
    elif 'today' in lower: date = reference.date()
    else:
        for name, weekday in WEEKDAYS.items():
            if re.search(r'\b' + name + r'\b', lower):
                delta = (weekday - reference.weekday()) % 7 or 7
                if 'next ' + name in lower and delta < 7: delta += 7
                date = reference.date() + timedelta(days=delta)
                break
        iso = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', text)
        if iso:
            try: date = datetime.fromisoformat(iso.group(1)).date()
            except ValueError: pass
        month = re.search(r'\b(' + '|'.join(MONTHS) + r')\s+(\d{1,2})(?:st|nd|rd|th)?\b', lower)
        if month:
            try:
                date = datetime(reference.year, MONTHS[month.group(1)], int(month.group(2))).date()
                if date < reference.date(): date = date.replace(year=date.year+1)
            except ValueError: pass
    return datetime.combine(date, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc).isoformat() if date else None

def tokenize(text: str) -> set[str]:
    return {word for word in re.findall(r'[a-z0-9]+', text.lower()) if word not in STOPWORDS and len(word) > 2}

def extract_rule_based(segments, participants: list[str], occurred_at: datetime) -> MeetingIntelligence:
    decisions, tasks, questions, risks = [], [], [], []
    names = sorted(set(participants) | {s.speaker for s in segments if s.speaker != 'Unknown speaker'}, key=len, reverse=True)
    topics = []
    for segment in segments:
        text = segment.text.strip()
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if not sentence: continue
            lower = sentence.lower()
            if re.search(r'\b(we (?:decided|agreed)|decision:|we will keep|let’s keep|let\'s keep|we approved)\b', lower):
                decisions.append(DecisionInput(text=sentence, source_segment_ids=[segment.id]))
            if '?' in sentence or re.search(r'\b(open question|unresolved|to be confirmed|tbd)\b', lower): questions.append(sentence)
            if re.search(r'\b(risk|blocker|blocked|concern|missed deadline|not yet validated)\b', lower): risks.append(sentence)
            explicit_owner = next((name for name in names if re.search(r'\b' + re.escape(name) + r'\s+(?:will|can|owns|should|needs to|is responsible for)\b', sentence, re.I) or re.search(r'\b' + re.escape(name.split()[0]) + r'\s+(?:will|can|owns|should|needs to|is responsible for)\b', sentence, re.I) or re.search(r'(?:assigned to|owner:)\s+' + re.escape(name) + r'\b', sentence, re.I)), None)
            first_person = bool(re.search(r'\b(i’ll|i\'ll|i will|i can|i own)\b', lower))
            owner = (segment.speaker if segment.speaker != 'Unknown speaker' else None) if first_person else explicit_owner
            commitment = bool(re.search(r'\b(will|need to|needs to|should|must|action item:|todo:|i’ll|i\'ll|i can|by friday|by monday|by tuesday|by wednesday|by thursday)\b', lower))
            if sentence.endswith('?') and not re.search(r'\b(action item:|todo:)\b', lower): continue
            if not commitment or sentence in [d.text for d in decisions]: continue
            title = sentence
            if owner:
                first = re.escape(owner.split()[0])
                title = re.sub(r'^' + first + r'\s+(?:will|can|should|needs to|will handle)\s+', '', title, flags=re.I)
                title = re.sub(r'\b' + first + r'\s+(?:will|can|should|needs to)\s+', '', title, flags=re.I)
            title = re.sub(r'^(?:i’ll|i\'ll|i will|i can|we need to|we should|we must|please|action item:|todo:)\s+', '', title, flags=re.I)
            title = re.sub(r'\s+by\s+(?:next\s+)?(?:' + '|'.join(WEEKDAYS) + r'|today|tomorrow|20\d{2}-\d{2}-\d{2}).*$', '', title, flags=re.I)
            title = title.strip(' .,;').rstrip('.')
            if not title: continue
            title = title[0].upper() + title[1:240]
            deadline = resolve_deadline(sentence, occurred_at)
            priority = 'urgent' if re.search(r'\b(urgent|asap|critical)\b', lower) else 'high' if re.search(r'\b(high priority|before launch|must)\b', lower) else 'medium'
            confidence = 0.94 if owner and deadline else 0.82 if owner else 0.64
            dependencies = []
            dependency_match = re.search(r'(?:depends on|waiting for|after|needs)\s+(?:the\s+)?([^,.]+)', sentence, re.I)
            if dependency_match: dependencies.append(dependency_match.group(1).strip())
            tasks.append(ExtractedTask(title=title, description=sentence, assignee=owner, deadline=deadline, priority=priority, dependencies=dependencies, source_segment_ids=[segment.id], confidence=confidence))
    # Deduplicate equivalent commitments, keeping their original evidence.
    unique = {}
    for task in tasks:
        key = task.title.casefold()
        if key not in unique: unique[key] = task
    tasks = list(unique.values())
    summaries = [d.text for d in decisions[:3]]
    summary = ('The discussion covered ' + ', '.join(topics[:4]) + '. ' if topics else '') + ('Key agreements: ' + ' '.join(summaries) + ' ' if summaries else '') + f'{len(tasks)} potential commitments were identified. ' + ('Review the source references and confirm missing owners or dates before approval.' if tasks else 'No explicit commitments were identified; review the transcript before adding tasks.')
    if not summary.strip(): summary = 'No discussion content was available.'
    next_steps = ['Confirm uncertain owners and deadlines.', 'Review and approve the proposed tasks.'] if tasks else ['Review the transcript and add next steps manually.']
    return MeetingIntelligence(summary=summary, topics=topics, decisions=decisions, questions=list(dict.fromkeys(questions)), risks=list(dict.fromkeys(risks)), next_steps=next_steps, tasks=tasks)
