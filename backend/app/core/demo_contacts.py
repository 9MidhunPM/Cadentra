"""Explicit delivery policy for imported fictional demo contacts.

The durable audit marker follows a customer even if an operator edits its email.
It is separate from the address JSON and never changes ordinary SMTP settings.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent

DEMO_CONTACT_DOMAIN = "demo.cadentra.example.com"
DEMO_CONTACT_ENTITY_TYPE = "CUSTOMER"
DEMO_CONTACT_ACTION = "DEMO_CONTACT_NO_EMAIL"


def is_demo_contact(
    db: Session, *, customer_id: UUID | None = None, recipient: str | None = None
) -> bool:
    """Deny the reserved demo domain or an explicitly marked imported customer."""
    if isinstance(recipient, str):
        domain = recipient.rpartition("@")[2].strip().casefold().rstrip(".")
        if domain == DEMO_CONTACT_DOMAIN or domain.endswith(f".{DEMO_CONTACT_DOMAIN}"):
            return True
    if customer_id is None:
        return False
    return db.scalar(
        select(AuditEvent.id)
        .where(
            AuditEvent.entity_type == DEMO_CONTACT_ENTITY_TYPE,
            AuditEvent.entity_id == customer_id,
            AuditEvent.action == DEMO_CONTACT_ACTION,
        )
        .limit(1)
    ) is not None
