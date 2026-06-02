from app.services.state_machine import (
    OrderStatus,
    StepStatus,
    can_confirm_order,
    can_generate_work_order,
    can_start_step,
    validate_inspection_result,
)


def test_order_must_be_confirmed_before_work_order_generation():
    assert can_generate_work_order(OrderStatus.DRAFT).allowed is False
    assert can_generate_work_order(OrderStatus.CONFIRMED).allowed is True


def test_order_can_only_confirm_from_draft():
    assert can_confirm_order(OrderStatus.DRAFT).allowed is True
    assert can_confirm_order(OrderStatus.IN_PRODUCTION).allowed is False


def test_step_requires_previous_finished_status():
    assert can_start_step(StepStatus.PENDING_PROCESS, StepStatus.PROCESSING).allowed is False
    assert can_start_step(StepStatus.PENDING_PROCESS, StepStatus.COMPLETED).allowed is True


def test_failed_inspection_requires_reason_and_rework_target():
    assert validate_inspection_result("failed", None, None).allowed is False
    assert validate_inspection_result("failed", "尺寸不符", "step-id").allowed is True
