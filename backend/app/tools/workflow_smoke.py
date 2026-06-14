from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.workflow_v2 import _record_business_node_action
from app.db import base as _model_registry  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.db.session import SessionLocal
from app.models.customer import Customer
from app.models.logistics import DeliveryOrder
from app.models.rbac import User
from app.models.sales import SalesOrder, SalesOrderItem
from app.models.workflow_v2 import FinanceBill, OrderWorkflowNode, SignRecord
from app.schemas.workflow_v2 import WorkflowNodeActionRequest
from app.services.workflow_v2 import (
    check_join,
    complete_epin_batch,
    complete_making_assignment,
    complete_node,
    create_making_assignments,
    get_workflow_for_order,
    receive_epin_batch,
    start_workflow_for_order,
    submit_making_assignment_to_epin,
)


PROCESSING_NODE_CODES = (
    "roll_bending",
    "flange_plate",
    "lathe",
    "basic_grinding",
    "copper_plating",
    "copper_grinding",
)

FINAL_NODE_CODES = (
    "join_before_engraving",
    "engraving",
    "chrome_plating",
    "proofing",
    "inspection",
)


class WorkflowSmokeError(RuntimeError):
    pass


class WorkflowSmokeRunner:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.suffix = uuid4().hex[:8].upper()
        self.order: SalesOrder | None = None

    def run(self) -> None:
        manager = self.user_by_username("xiang") or self.user_by_username("admin")
        if manager is None:
            raise WorkflowSmokeError("Missing xiang/admin user for workflow smoke.")

        maker = self.user_by_role({"operator", "designer"})
        if maker is None:
            raise WorkflowSmokeError("No active operator/designer account available for making assignment.")

        epin_user = self.user_by_role({"operator"}, department_keywords=("epin", "电拼")) or maker

        self.order = self.create_order(manager)
        start_workflow_for_order(self.db, self.order)
        self.db.flush()
        self.pass_step("workflow started")

        assignments = create_making_assignments(
            self.db,
            sales_order=self.order,
            supervisor_id=manager.id,
            assignments=[(maker.id, 1, "workflow smoke assignment")],
        )
        if len(assignments) != 1:
            raise WorkflowSmokeError("Making assignment was not created.")
        assignment = complete_making_assignment(self.db, assignments[0], 1, "workflow smoke making complete")
        batch = submit_making_assignment_to_epin(self.db, assignment)
        batch = receive_epin_batch(self.db, batch, epin_user.id)
        complete_epin_batch(self.db, batch, "workflow smoke epin complete")
        self.db.flush()
        self.pass_step("making and epin completed")

        for node_code in PROCESSING_NODE_CODES:
            self.complete_node_code(node_code)
        join = check_join(self.db, self.order.id)
        if not join.ready:
            raise WorkflowSmokeError(f"Join node is not ready; waiting for: {', '.join(join.waiting_for)}")
        self.pass_step("parallel processing reached join")

        for node_code in FINAL_NODE_CODES:
            self.complete_node_code(node_code)

        self.complete_business_node(
            "finance_bill",
            manager,
            WorkflowNodeActionRequest(
                bill_no=f"SMOKE-BILL-{self.suffix}",
                delivery_note_no=f"SMOKE-DN-{self.suffix}",
                bill_amount=100,
                remarks="workflow smoke finance bill",
            ),
        )
        self.complete_business_node(
            "delivery",
            manager,
            WorkflowNodeActionRequest(
                delivery_time=datetime.now(timezone.utc),
                delivery_person="Workflow Smoke",
                delivery_address="Workflow smoke address",
                logistics=f"SMOKE-LOG-{self.suffix}",
                remarks="workflow smoke delivery",
            ),
        )
        self.complete_business_node(
            "sign",
            manager,
            WorkflowNodeActionRequest(
                signer="Workflow Smoke Customer",
                signed_at=datetime.now(timezone.utc),
                sign_proof_no=f"SMOKE-SIGN-{self.suffix}",
                remarks="workflow smoke sign",
            ),
        )

        workflow = get_workflow_for_order(self.db, self.order.id)
        if workflow.status != "completed":
            raise WorkflowSmokeError(f"Workflow status should be completed, got {workflow.status}.")

        if not self.db.query(FinanceBill.id).filter(FinanceBill.sales_order_id == self.order.id).first():
            raise WorkflowSmokeError("Finance bill was not created.")
        delivery = self.db.query(DeliveryOrder).filter(DeliveryOrder.sales_order_id == self.order.id).first()
        if delivery is None or delivery.status != "signed":
            raise WorkflowSmokeError("Delivery order should exist and be signed.")
        if not self.db.query(SignRecord.id).filter(SignRecord.sales_order_id == self.order.id).first():
            raise WorkflowSmokeError("Sign record was not created.")

        self.pass_step("finance, delivery, sign, and completion verified")

    def create_order(self, manager: User) -> SalesOrder:
        customer = Customer(
            customer_code=f"SMOKE-CU-{self.suffix}",
            name=f"Workflow Smoke Customer {self.suffix}",
            contact_name="Workflow Smoke",
            address="Workflow smoke address",
            salesperson_id=manager.id,
            payment_terms_days=30,
            status="active",
        )
        self.db.add(customer)
        self.db.flush()

        order = SalesOrder(
            order_no=f"SMOKE-SO-{self.suffix}",
            customer_id=customer.id,
            product_summary="Workflow smoke cylinder",
            order_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=100,
            status="confirmed",
            priority="normal",
            plate_details={
                "order_type": "old_cylinder",
                "sample_no": f"SMOKE-{self.suffix}",
                "cylinder_id": f"SMOKE-{self.suffix}",
                "total_qty": 1,
            },
            remark="Created by workflow smoke; default run rolls back.",
            created_by=manager.id,
        )
        order.items.append(
            SalesOrderItem(
                product_name="Workflow smoke cylinder",
                specification="Smoke spec",
                quantity=1,
                unit="set",
                unit_price=100,
                amount=100,
            )
        )
        self.db.add(order)
        self.db.flush()
        return order

    def user_by_username(self, username: str) -> User | None:
        return (
            self.db.query(User)
            .options(selectinload(User.roles))
            .filter(User.username == username, User.status == "active", User.deleted_at.is_(None))
            .first()
        )

    def user_by_role(self, role_codes: set[str], department_keywords: tuple[str, ...] = ()) -> User | None:
        users = (
            self.db.query(User)
            .options(selectinload(User.roles))
            .filter(User.status == "active", User.deleted_at.is_(None))
            .order_by(User.username.asc())
            .all()
        )
        for user in users:
            roles = {role.code for role in user.roles}
            if not roles & role_codes:
                continue
            if department_keywords:
                department = (user.department or "").casefold()
                if not any(keyword.casefold() in department for keyword in department_keywords):
                    continue
            return user
        return None

    def node_by_code(self, node_code: str) -> OrderWorkflowNode:
        if self.order is None:
            raise WorkflowSmokeError("Order has not been created.")
        node = (
            self.db.query(OrderWorkflowNode)
            .filter(
                OrderWorkflowNode.sales_order_id == self.order.id,
                OrderWorkflowNode.node_code == node_code,
                OrderWorkflowNode.deleted_at.is_(None),
            )
            .first()
        )
        if node is None:
            raise WorkflowSmokeError(f"Workflow node not found: {node_code}")
        return node

    def complete_node_code(self, node_code: str) -> None:
        node = self.node_by_code(node_code)
        if node.status not in {"active", "in_progress", "waiting"}:
            raise WorkflowSmokeError(f"Node {node_code} is not ready; status={node.status}.")
        complete_node(self.db, node, remarks=f"workflow smoke complete {node_code}")
        self.db.flush()
        self.pass_step(f"node completed: {node_code}")

    def complete_business_node(self, node_code: str, user: User, payload: WorkflowNodeActionRequest) -> None:
        node = self.node_by_code(node_code)
        if node.status not in {"active", "in_progress", "waiting"}:
            raise WorkflowSmokeError(f"Business node {node_code} is not ready; status={node.status}.")
        _record_business_node_action(self.db, node, payload, user)
        complete_node(self.db, node, remarks=payload.remarks)
        self.db.flush()
        self.pass_step(f"business node completed: {node_code}")

    def pass_step(self, message: str) -> None:
        print(f"[PASS] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the workflow v2 full-path smoke check.")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit the smoke customer/order instead of rolling it back. Default is rollback.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        runner = WorkflowSmokeRunner(db)
        runner.run()
        if args.commit:
            db.commit()
            print("\nWorkflow smoke passed and committed.")
        else:
            db.rollback()
            print("\nWorkflow smoke passed; transaction rolled back.")
        return 0
    except HTTPException as exc:
        db.rollback()
        print(f"\nWorkflow smoke failed: HTTP {exc.status_code}: {exc.detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - smoke script should report the root failure
        db.rollback()
        print(f"\nWorkflow smoke failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
