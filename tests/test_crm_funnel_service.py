from core.crm.service import CRMService
from core.users.models import User


def test_stage_new_to_engaged_on_message():
    assert CRMService.stage_after_message(User.CRM_STAGE_NEW) == User.CRM_STAGE_ENGAGED


def test_contacts_set_ready_to_pay():
    assert CRMService.stage_after_contacts(User.CRM_STAGE_ENGAGED) == User.CRM_STAGE_READY_TO_PAY


def test_payment_paid_sets_paid_stage():
    assert CRMService.stage_after_payment_paid(User.CRM_STAGE_READY_TO_PAY) == User.CRM_STAGE_PAID
