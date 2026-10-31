CATALOG = {
    'gmail': {'name': 'Gmail', 'description': 'Turn commitments into thoughtful follow-up drafts.', 'implemented': True, 'oauth': 'google', 'scopes': ['https://www.googleapis.com/auth/gmail.compose'], 'action': 'gmail_draft'},
    'google_calendar': {'name': 'Google Calendar', 'description': 'Give the next conversation a place on the calendar.', 'implemented': True, 'oauth': 'google', 'scopes': ['https://www.googleapis.com/auth/calendar.events'], 'action': 'calendar_event'},
    'slack': {'name': 'Slack', 'description': 'Keep the team in the loop, with your approval.', 'implemented': True, 'oauth': 'slack', 'scopes': ['chat:write'], 'action': 'slack_message'},
    'linear': {'name': 'Linear', 'description': 'Move from a clear commitment to a tracked issue.', 'implemented': True, 'oauth': 'linear', 'scopes': ['write'], 'action': 'linear_issue'},
    'notion': {'name': 'Notion', 'description': 'Bring meeting decisions into your team’s knowledge base.', 'implemented': True, 'oauth': 'notion', 'scopes': [], 'action': 'notion_page'},
    'teams': {'name': 'Microsoft Teams', 'description': 'Meeting capture and approved team updates.', 'implemented': False},
    'trello': {'name': 'Trello', 'description': 'Bring visual project boards into the loop.', 'implemented': False},
    'asana': {'name': 'Asana', 'description': 'Connect commitments to your portfolio of work.', 'implemented': False},
}

def oauth_credentials(provider: str):
    from core.config import get_settings
    s = get_settings()
    family = CATALOG[provider]['oauth'] if provider in CATALOG else provider
    return getattr(s, f'{family}_client_id', ''), getattr(s, f'{family}_client_secret', '')

def redirect_uri(provider: str):
    from core.config import get_settings
    return f'{get_settings().api_public_url.rstrip("/")}/api/integrations/{provider}/callback'
