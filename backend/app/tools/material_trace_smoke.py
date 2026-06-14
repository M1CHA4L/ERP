from __future__ import annotations

import argparse
import sys
from datetime import date
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.sales_orders import _use_customer_materials_for_order, list_sales_order_material_uses
from app.db import base as _model_registry  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.db.session import SessionLocal
from app.models.customer import Customer
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.rbac import User
from app.models.sales import SalesOrder, SalesOrderItem
from app.schemas.sales import SalesOrderCustomerMaterialUseCreate
from app.services.state_machine import OrderStatus
from app.services.timeline import build_sales_order_timeline


class MaterialTraceSmokeError(RuntimeError):
    pass


class MaterialTraceSmokeRunner:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.suffix = uuid4().hex[:8].upper()
        self.user: User | None = None
        self.customer: Customer | None = None
        self.lot: InventoryLot | None = None
        self.order: SalesOrder | None = None

    def run(self) -> None:
        self.user = self.user_by_username("xiang") or self.user_by_username("admin")
        if self.user is None:
            raise MaterialTraceSmokeError("Missing xiang/admin user for material trace smoke.")

        self.customer = self.create_customer()
        self.lot = self.create_customer_material_lot()
        self.order = self.create_order()
        self.db.flush()
        self.pass_step("seed customer, material lot, and order")

        used_count = _use_customer_materials_for_order(
            self.db,
            self.order,
            [
                SalesOrderCustomerMaterialUseCreate(
                    lot_id=self.lot.id,
                    quantity=2,
                    remark="material trace smoke use",
                )
            ],
            self.user,
        )
        self.db.flush()
        if used_count != 1:
            raise MaterialTraceSmokeError(f"Expected one material use, got {used_count}.")
        if float(self.lot.quantity_on_hand) != 3:
            raise MaterialTraceSmokeError(f"Expected lot quantity 3 after use, got {self.lot.quantity_on_hand}.")
        self.pass_step("customer material deducted")

        transaction_count = (
            self.db.query(InventoryTransaction)
            .filter(InventoryTransaction.sales_order_id == self.order.id, InventoryTransaction.deleted_at.is_(None))
            .count()
        )
        if transaction_count != 1:
            raise MaterialTraceSmokeError(f"Expected one inventory transaction, got {transaction_count}.")
        self.pass_step("inventory transaction created")

        material_uses = list_sales_order_material_uses(self.order.id, db=self.db, current_user=self.user)
        if len(material_uses) != 1:
            raise MaterialTraceSmokeError(f"Expected one order material use record, got {len(material_uses)}.")
        material_use = material_uses[0]
        material_fields = set(material_use.model_dump().keys())
        if {"unit_price", "total_amount", "cost"} & material_fields:
            raise MaterialTraceSmokeError("Order material use response should not expose cost fields.")
        if material_use.lot_no != self.lot.lot_no or material_use.quantity_used != 2:
            raise MaterialTraceSmokeError("Order material use response has unexpected lot or quantity.")
        self.pass_step("order material use endpoint verified")

        timeline = build_sales_order_timeline(self.db, self.order)
        material_events = [item for item in timeline if item.category == "material"]
        if len(material_events) != 1:
            raise MaterialTraceSmokeError(f"Expected one material timeline event, got {len(material_events)}.")
        if material_events[0].meta.get("lot_no") != self.lot.lot_no:
            raise MaterialTraceSmokeError("Material timeline event should include lot_no metadata.")
        self.pass_step("material timeline event verified")

    def user_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username, User.status == "active").first()

    def create_customer(self) -> Customer:
        customer = Customer(
            customer_code=f"SMOKE-MAT-CU-{self.suffix}",
            name=f"Material Trace Smoke Customer {self.suffix}",
            payment_terms_days=30,
            status="active",
        )
        self.db.add(customer)
        self.db.flush()
        return customer

    def create_customer_material_lot(self) -> InventoryLot:
        if self.customer is None:
            raise MaterialTraceSmokeError("Customer has not been created.")
        lot = InventoryLot(
            lot_no=f"SMOKE-MAT-LOT-{self.suffix}",
            owner_type="customer",
            customer_id=self.customer.id,
            warehouse_name="Smoke Warehouse",
            product_name="Smoke Film",
            specification="1000mm",
            unit="pcs",
            quantity_on_hand=5,
            unit_price=2,
            status="available",
        )
        self.db.add(lot)
        self.db.flush()
        return lot

    def create_order(self) -> SalesOrder:
        if self.customer is None or self.user is None:
            raise MaterialTraceSmokeError("Customer and user must exist before creating order.")
        order = SalesOrder(
            order_no=f"SMOKE-MAT-SO-{self.suffix}",
            customer_id=self.customer.id,
            product_summary="Smoke Film",
            order_date=date.today(),
            due_date=date.today(),
            total_amount=0,
            status=OrderStatus.DRAFT,
            priority="normal",
            plate_details={"cylinder_id": f"SMOKE-CYL-{self.suffix}", "material": "self-bring"},
            color_rows=[],
            remark="Created by material trace smoke; default run rolls back.",
            created_by=self.user.id,
        )
        order.items.append(
            SalesOrderItem(
                product_name="Smoke Film",
                specification="1000mm",
                quantity=1,
                unit="pcs",
                unit_price=0,
                amount=0,
            )
        )
        self.db.add(order)
        self.db.flush()
        return order

    def pass_step(self, name: str) -> None:
        print(f"[PASS] {name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the customer material trace smoke check.")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit smoke data instead of rolling it back. Intended only for manual debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        runner = MaterialTraceSmokeRunner(db)
        runner.run()
        if args.commit:
            db.commit()
            print("\nMaterial trace smoke passed and committed.")
        else:
            db.rollback()
            print("\nMaterial trace smoke passed; transaction rolled back.")
        return 0
    except HTTPException as exc:
        db.rollback()
        print(f"\nMaterial trace smoke failed: HTTP {exc.status_code}: {exc.detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - smoke script should report the root failure
        db.rollback()
        print(f"\nMaterial trace smoke failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
