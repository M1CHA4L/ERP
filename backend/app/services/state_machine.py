from dataclasses import dataclass


class OrderStatus:
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    IN_PRODUCTION = "in_production"
    PENDING_INSPECTION = "pending_inspection"
    INSPECTION_PASSED = "inspection_passed"
    PENDING_DELIVERY = "pending_delivery"
    DELIVERED = "delivered"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    REWORKING = "reworking"


class WorkOrderStatus:
    PENDING_SCHEDULE = "pending_schedule"
    SCHEDULED = "scheduled"
    IN_PRODUCTION = "in_production"
    PARTIAL_COMPLETED = "partial_completed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REWORKING = "reworking"


class StepStatus:
    NOT_STARTED = "not_started"
    PENDING_PROCESS = "pending_process"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PENDING_INSPECTION = "pending_inspection"
    INSPECTION_PASSED = "inspection_passed"
    INSPECTION_FAILED = "inspection_failed"
    REWORKING = "reworking"
    SKIPPED = "skipped"


class FinanceStatus:
    NOT_CREATED = "not_created"
    PENDING_INVOICE = "pending_invoice"
    INVOICED = "invoiced"
    PARTIAL_PAID = "partial_paid"
    PAID = "paid"
    CLOSED = "closed"
    OVERDUE = "overdue"


FINISHED_STEP_STATUSES = {
    StepStatus.COMPLETED,
    StepStatus.INSPECTION_PASSED,
    StepStatus.SKIPPED,
}


@dataclass(frozen=True)
class TransitionResult:
    allowed: bool
    reason: str = ""


def can_confirm_order(status: str) -> TransitionResult:
    if status != OrderStatus.DRAFT:
        return TransitionResult(False, "Only draft orders can be confirmed.")
    return TransitionResult(True)


def can_generate_work_order(order_status: str) -> TransitionResult:
    if order_status != OrderStatus.CONFIRMED:
        return TransitionResult(False, "Work orders can only be generated after order confirmation.")
    return TransitionResult(True)


def can_start_step(current_status: str, previous_status: str | None) -> TransitionResult:
    if current_status != StepStatus.PENDING_PROCESS:
        return TransitionResult(False, "Only pending process steps can be started.")
    if previous_status is not None and previous_status not in FINISHED_STEP_STATUSES:
        return TransitionResult(False, "Previous step must be completed, passed, or skipped.")
    return TransitionResult(True)


def next_status_after_complete(requires_inspection: bool) -> str:
    return StepStatus.PENDING_INSPECTION if requires_inspection else StepStatus.COMPLETED


def validate_inspection_result(result: str, reason: str | None, rework_to_step_id: str | None) -> TransitionResult:
    if result in {"failed", "rework"}:
        if not reason:
            return TransitionResult(False, "Failed or rework inspection must include a reason.")
        if not rework_to_step_id:
            return TransitionResult(False, "Failed or rework inspection must select a target rework step.")
    return TransitionResult(True)
