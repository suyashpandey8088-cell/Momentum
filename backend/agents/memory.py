import math
import re
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from models.entities import Memory, Task, Meeting, Participant, now
from agents.intelligence import tokenize
from services.providers import embedding_provider
from services.common import utc

def embed_memories(db: Session, org_id: str):
    provider = embedding_provider()
    if not provider: return
    items = list(db.scalars(select(Memory).where(Memory.organization_id == org_id, Memory.embedding_provider == 'lexical').limit(64)))
    if not items: return
    vectors = provider.embed([item.content[:12000] for item in items])
    for item, vector in zip(items, vectors):
        item.embedding = vector
        item.embedding_provider = provider.name

def retrieve(db: Session, org_id: str, question: str, project_id: str | None = None, limit: int = 6):
    provider = embedding_provider()
    query_vector = None
    if provider:
        try: query_vector = provider.embed([question])[0]
        except Exception: pass
    if query_vector and db.bind.dialect.name == 'postgresql':
        query = 'SELECT id, 1 - (embedding <=> CAST(:vector AS vector)) AS score FROM memories WHERE organization_id = :org AND embedding IS NOT NULL'
        params = {'vector': str(query_vector), 'org': org_id, 'limit': limit}
        if project_id: query += ' AND project_id = :project'; params['project'] = project_id
        query += ' ORDER BY embedding <=> CAST(:vector AS vector) LIMIT :limit'
        rows = db.execute(text(query), params).all()
        return [(db.get(Memory, row.id), max(0.0, min(1.0, float(row.score)))) for row in rows]
    items = list(db.scalars(select(Memory).where(Memory.organization_id == org_id).order_by(Memory.created_at.desc()).limit(10000)))
    words = tokenize(question)
    scored = []
    for item in items:
        if project_id and item.project_id != project_id: continue
        overlap = words & tokenize(item.content + ' ' + item.source_label)
        lexical = len(overlap) / max(1, math.sqrt(len(words) * len(tokenize(item.content))))
        score = lexical
        if query_vector and item.embedding and len(item.embedding) == len(query_vector):
            dot = sum(a*b for a,b in zip(query_vector, item.embedding))
            norm = math.sqrt(sum(a*a for a in query_vector)*sum(b*b for b in item.embedding))
            score = max(0, dot/norm) if norm else 0
        if score > 0: scored.append((item, score))
    scored.sort(key=lambda entry: entry[1], reverse=True)
    return scored[:limit]

def answer_memory(db: Session, org_id: str, question: str, project_id: str | None = None):
    results = retrieve(db, org_id, question, project_id)
    mode = 'Semantic retrieval' if results and results[0][0].embedding_provider != 'lexical' else 'Lexical retrieval'
    if not results: return {'answer': 'I couldn’t find a relevant commitment in this workspace. Try a project name or a phrase from the original discussion. I won’t fill in the gaps with a guess.', 'mode': mode, 'sources': [], 'related_tasks': []}
    lines = ['Here’s the relevant history I found, with its current execution status:']
    sources, task_ids = [], set()
    for memory, score in results:
        line = memory.content
        if memory.task_id:
            task = db.get(Task, memory.task_id)
            if task and task.organization_id == org_id:
                owner = db.get(Participant, task.assignee_id) if task.assignee_id else None
                deadline = utc(task.deadline)
                status = 'overdue' if deadline and deadline < now() and task.status != 'completed' else task.status
                line += f' Current status: {status.replace("_", " ")}.'
                if owner: line += f' Owner: {owner.name}.'
                if deadline: line += f' Deadline: {deadline.strftime("%b %d, %Y")}.'
                if task.id not in task_ids: task_ids.add(task.id)
        lines.append(line)
        if memory.meeting_id and not any(s['meeting_id'] == memory.meeting_id for s in sources):
            meeting = db.get(Meeting, memory.meeting_id)
            if meeting: sources.append({'meeting_id': meeting.id, 'title': meeting.title, 'date': utc(meeting.occurred_at).isoformat(), 'excerpt': memory.content[:500], 'relevance': round(score, 3)})
    related = [db.get(Task, task_id) for task_id in task_ids]
    from services.common import task_data
    return {'answer': '\n\n'.join(lines), 'mode': mode + ' · grounded in workspace records', 'sources': sources, 'related_tasks': [task_data(task, db) for task in related if task]}
