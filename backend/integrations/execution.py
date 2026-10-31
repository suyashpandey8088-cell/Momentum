import base64
from email.message import EmailMessage
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.entities import Integration
from .oauth import access_token


def execute_external(db: Session, integration: Integration, kind: str, payload: dict) -> dict:
    token = access_token(db, integration)
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        with httpx.Client(timeout=30) as client:
            if kind == 'gmail_draft':
                message = EmailMessage(); message['To'] = payload['to']; message['Subject'] = payload['subject']; message.set_content(payload['body'])
                raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
                response = client.post('https://gmail.googleapis.com/gmail/v1/users/me/drafts', headers=headers, json={'message': {'raw': raw}}); response.raise_for_status()
                result = response.json(); external_id = result['id']
                verified = client.get(f'https://gmail.googleapis.com/gmail/v1/users/me/drafts/{external_id}', headers=headers); verified.raise_for_status()
                return {'id': external_id, 'verified': True, 'message': 'Draft created and verified in Gmail. Nothing was sent.', 'url': 'https://mail.google.com/mail/u/0/#drafts'}
            if kind == 'calendar_event':
                body = {'summary': payload['title'], 'description': payload.get('description', ''), 'start': {'dateTime': payload['start'], 'timeZone': 'UTC'}, 'end': {'dateTime': payload['end'], 'timeZone': 'UTC'}, 'attendees': [{'email': email} for email in payload.get('attendees', [])]}
                response = client.post('https://www.googleapis.com/calendar/v3/calendars/primary/events', headers=headers, json=body); response.raise_for_status()
                result = response.json(); external_id = result['id']
                verified = client.get(f'https://www.googleapis.com/calendar/v3/calendars/primary/events/{external_id}', headers=headers); verified.raise_for_status()
                return {'id': external_id, 'verified': True, 'message': 'Calendar event created and verified.', 'url': result.get('htmlLink', '')}
            if kind == 'linear_issue':
                query = 'mutation CreateIssue($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id identifier url } } }'
                response = client.post('https://api.linear.app/graphql', headers=headers, json={'query': query, 'variables': {'input': {'teamId': payload['team_id'], 'title': payload['title'], 'description': payload.get('description', '')}}}); response.raise_for_status()
                result = response.json()
                if result.get('errors') or not result.get('data', {}).get('issueCreate', {}).get('success'): raise ValueError('Linear did not confirm issue creation.')
                issue = result['data']['issueCreate']['issue']
                return {'id': issue['id'], 'verified': True, 'message': f'Issue {issue["identifier"]} created in Linear.', 'url': issue['url']}
            if kind == 'notion_page':
                headers['Notion-Version'] = '2022-06-28'
                content = payload.get('description', '')
                chunks = [content[i:i+1800] for i in range(0, len(content), 1800)] or ['']
                body = {'parent': {'database_id': payload['database_id']}, 'properties': {payload.get('title_property', 'Name'): {'title': [{'text': {'content': payload['title']}}]}}, 'children': [{'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': [{'type': 'text', 'text': {'content': chunk}}]}} for chunk in chunks[:50]]}
                response = client.post('https://api.notion.com/v1/pages', headers=headers, json=body); response.raise_for_status(); result = response.json()
                verified = client.get(f'https://api.notion.com/v1/pages/{result["id"]}', headers=headers); verified.raise_for_status()
                return {'id': result['id'], 'verified': True, 'message': 'Page created and verified in Notion.', 'url': result.get('url', '')}
            if kind == 'slack_message':
                response = client.post('https://slack.com/api/chat.postMessage', headers=headers, json={'channel': payload['channel'], 'text': payload['text'], 'unfurl_links': False}); response.raise_for_status(); result = response.json()
                if not result.get('ok'): raise ValueError('Slack did not confirm the message.')
                return {'id': result['ts'], 'verified': True, 'message': 'Slack acknowledged the approved message.', 'channel': result['channel'], 'url': ''}
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status in (401, 403): integration.status = 'error'; db.commit()
        raise HTTPException(502, f'The provider returned HTTP {status}. Check its permissions and configuration. The action was not confirmed.')
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise HTTPException(502, 'The provider did not confirm this action. Check the destination before retrying; an external request may have been received.')
    raise HTTPException(422, 'Unsupported execution type.')
