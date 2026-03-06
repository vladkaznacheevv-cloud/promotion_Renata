from core.db import Base
from core.users.models import User
from core.consultations.models import Consultation, UserConsultation
from core.events.models import Event, UserEvent
from core.payments.models import Payment
from core.crm.models import (
    ClientActivityLog,
    CRMUserActivity,
    IntegrationState,
    ChannelInvite,
    UserSubscription,
    YooKassaPayment,
    YooKassaWebhookEvent,
)
from core.auth.models import AdminUser
from core.catalog.models import CatalogItem

__all__ = [
    "Base",
    "User",
    "Consultation",
    "UserConsultation",
    "Event",
    "UserEvent",
    "Payment",
    "CRMUserActivity",
    "ClientActivityLog",
    "IntegrationState",
    "ChannelInvite",
    "UserSubscription",
    "YooKassaPayment",
    "YooKassaWebhookEvent",
    "AdminUser",
    "CatalogItem",
]

from core.consultations import models as _consultations_models  # noqa: F401
