import smtplib
import ssl
import logging
from email.message import EmailMessage
from sqlalchemy.orm import Session
from models.entities import EmailOutbox
from core.config import get_settings

logger = logging.getLogger('momentum.email')

def send_email(db: Session, recipient: str, subject: str, body: str) -> str:
    settings = get_settings()
    item = EmailOutbox(recipient=recipient, subject=subject, body=body)
    db.add(item)
    if not settings.smtp_host:
        item.status = 'local_only'
        db.flush()
        return item.id
    message = EmailMessage()
    message['From'] = settings.smtp_from
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user: smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        item.status = 'sent'
    except Exception:
        item.status = 'failed'
        logger.exception('Email delivery failed')
    db.flush()
    return item.id
