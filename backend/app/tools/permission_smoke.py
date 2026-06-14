from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID
from uuid import uuid4

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.finance import Receivable
from app.models.logistics import DeliveryOrder
from app.models.production import WorkOrder
from app.models.rbac import Permission, Role, User

BASE_URL = os.getenv("PERMISSION_SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUIRED_USERS = ("admin", "xiang", "shohag", "farhad", "al_amin", "abdul_bari", "liang", "rana", "shen")
CROSS_DEPARTMENT_MANAGER_USERS = ("liang", "rana", "shen")


@dataclass
class ApiResult:
    status_code: int
    body: object | None


class SmokeRunner:
    def __init__(self) -> None:
        self.db = SessionLocal()
        self.failures: list[str] = []
        self.skips: list[str] = []
        self.users = {
            user.username: user
            for user in self.db.query(User).filter(User.username.in_(REQUIRED_USERS)).all()
        }

    def close(self) -> None:
        self.db.close()

    def token_for(self, username: str) -> str:
        user = self.users.get(username)
        if user is None:
            raise RuntimeError(f"Required user is missing: {username}")
        return create_access_token(str(user.id))

    def get(self, username: str, path: str) -> ApiResult:
        request = urllib.request.Request(
            f"{BASE_URL}{path}",
            headers={
                "Authorization": f"Bearer {self.token_for(username)}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw_body = response.read().decode("utf-8")
                status_code = response.status
        except urllib.error.HTTPError as error:
            raw_body = error.read().decode("utf-8")
            status_code = error.code

        try:
            body = json.loads(raw_body) if raw_body else None
        except json.JSONDecodeError:
            body = raw_body
        return ApiResult(status_code=status_code, body=body)

    def check(
        self,
        name: str,
        username: str,
        path: str,
        expected_status: int,
        validator: Callable[[object | None], str | None] | None = None,
    ) -> None:
        try:
            result = self.get(username, path)
        except Exception as exc:  # noqa: BLE001 - smoke script should report and continue
            self.failures.append(f"{name}: request failed: {exc}")
            print(f"[FAIL] {name}: request failed: {exc}")
            return

        if result.status_code != expected_status:
            self.failures.append(f"{name}: expected {expected_status}, got {result.status_code}")
            print(f"[FAIL] {name}: expected {expected_status}, got {result.status_code}")
            return

        if validator:
            message = validator(result.body)
            if message:
                self.failures.append(f"{name}: {message}")
                print(f"[FAIL] {name}: {message}")
                return

        print(f"[PASS] {name}: {username} {path} -> {result.status_code}")

    def skip(self, name: str, reason: str) -> None:
        self.skips.append(f"{name}: {reason}")
        print(f"[SKIP] {name}: {reason}")

    def check_cross_department_managers(self) -> None:
        for username in CROSS_DEPARTMENT_MANAGER_USERS:
            user = self.users.get(username)
            if user is None:
                self.failures.append(f"{username}: manager account is missing")
                print(f"[FAIL] {username}: manager account is missing")
                continue
            roles = {role.code for role in user.roles}
            missing = {"sales", "production_manager"} - roles
            if missing:
                self.failures.append(f"{username}: missing manager roles: {', '.join(sorted(missing))}")
                print(f"[FAIL] {username}: missing manager roles: {', '.join(sorted(missing))}")
                continue
            print(f"[PASS] {username}: cross-department manager roles are present")

    def check_user_permission_overrides(self) -> None:
        sales_role = self.db.query(Role).filter(Role.code == "sales", Role.status == "active").first()
        finance_permission = self.db.query(Permission).filter(Permission.code == "finance:receivable:view").first()
        order_create_permission = self.db.query(Permission).filter(Permission.code == "order:create").first()
        if sales_role is None or finance_permission is None or order_create_permission is None:
            self.failures.append("user permission overrides: required role or permission is missing")
            print("[FAIL] user permission overrides: required role or permission is missing")
            return

        user = User(
            username=f"smoke_permission_{uuid4().hex[:8]}",
            password_hash="smoke-only",
            real_name="Smoke Permission Override",
            department="Smoke",
            status="active",
        )
        user.roles = [sales_role]
        user.extra_permissions = [finance_permission]
        user.disabled_permissions = [order_create_permission]
        self.db.add(user)
        self.db.flush()

        permissions = user.permission_codes
        if "finance:receivable:view" not in permissions:
            self.failures.append("user permission overrides: extra permission is not effective")
            print("[FAIL] user permission overrides: extra permission is not effective")
            return
        if "order:create" in permissions:
            self.failures.append("user permission overrides: disabled permission is still effective")
            print("[FAIL] user permission overrides: disabled permission is still effective")
            return
        if "order:view" not in permissions:
            self.failures.append("user permission overrides: role permissions should remain effective")
            print("[FAIL] user permission overrides: role permissions should remain effective")
            return
        print("[PASS] user permission overrides: role + extra - disabled permissions are effective")

    def first_receivable_order_id(self) -> UUID | None:
        row = (
            self.db.query(Receivable.sales_order_id)
            .filter(Receivable.deleted_at.is_(None), Receivable.sales_order_id.isnot(None))
            .first()
        )
        return row[0] if row else None

    def first_delivery_id(self) -> UUID | None:
        row = self.db.query(DeliveryOrder.id).filter(DeliveryOrder.deleted_at.is_(None)).first()
        return row[0] if row else None

    def first_work_order_id(self) -> UUID | None:
        row = self.db.query(WorkOrder.id).filter(WorkOrder.deleted_at.is_(None)).first()
        return row[0] if row else None

    def run(self) -> int:
        missing_users = sorted(set(REQUIRED_USERS) - set(self.users))
        if missing_users:
            for username in missing_users:
                self.failures.append(f"Required user is missing: {username}")
                print(f"[FAIL] Required user is missing: {username}")
            return 1

        self.check_cross_department_managers()
        self.check_user_permission_overrides()
        self.check("admin can list full users", "admin", "/api/v1/users", 200, has_permissions)
        self.check("xiang boss/admin can list full users", "xiang", "/api/v1/users", 200, has_permissions)
        self.check("admin can list permissions", "admin", "/api/v1/users/permissions", 200, permissions_are_available)
        self.check("production manager cannot list permissions", "shohag", "/api/v1/users/permissions", 403)
        self.check("production manager cannot list full users", "shohag", "/api/v1/users", 403)
        self.check("production manager can load user options", "shohag", "/api/v1/users/options", 200, no_permissions)
        self.check("sales option picker is limited", "farhad", "/api/v1/users/options?role_code=sales", 200, only_sales_roles)
        self.check("sales can load product options", "farhad", "/api/v1/products/options", 200, product_options_are_minimal)
        self.check("old product export endpoint is removed", "admin", "/api/v1/products/export", 404)

        order_id = self.first_receivable_order_id()
        self.check("sales cannot list receivable ledger", "farhad", "/api/v1/finance/receivables?page_size=1", 403)
        if order_id:
            encoded_id = urllib.parse.quote(str(order_id))
            self.check(
                "sales can read receivable in order context",
                "farhad",
                f"/api/v1/finance/receivables?sales_order_id={encoded_id}&page_size=1",
                200,
            )
        else:
            self.skip("sales can read receivable in order context", "no receivable with sales_order_id")
        self.check("finance can list receivable ledger", "al_amin", "/api/v1/finance/receivables?page_size=1", 200)
        self.check("delivery cannot list receivable ledger", "abdul_bari", "/api/v1/finance/receivables?page_size=1", 403)
        self.check("sales cannot read daily receipts", "farhad", "/api/v1/finance/receipts/daily?page_size=1", 403)

        delivery_id = self.first_delivery_id()
        if delivery_id:
            self.check(
                "delivery can print no-amount delivery note",
                "abdul_bari",
                f"/api/v1/delivery-orders/{delivery_id}/print?variant=no_amount",
                200,
            )
            self.check(
                "delivery cannot print priced delivery note",
                "abdul_bari",
                f"/api/v1/delivery-orders/{delivery_id}/print?variant=priced",
                403,
            )
            self.check(
                "finance can print priced delivery note",
                "al_amin",
                f"/api/v1/delivery-orders/{delivery_id}/print?variant=priced",
                200,
            )
        else:
            self.skip("delivery print permissions", "no delivery order")

        work_order_id = self.first_work_order_id()
        if work_order_id:
            self.check(
                "production manager can print process task sheet",
                "shohag",
                f"/api/v1/work-orders/{work_order_id}/process-task-sheet",
                200,
            )
        else:
            self.skip("process task sheet permissions", "no work order")

        if self.failures:
            print(f"\nPermission smoke failed: {len(self.failures)} failure(s), {len(self.skips)} skipped.")
            return 1
        print(f"\nPermission smoke passed: {len(self.skips)} skipped.")
        return 0


def has_permissions(body: object | None) -> str | None:
    if not isinstance(body, list) or not body:
        return "expected a non-empty user list"
    if "permissions" not in body[0]:
        return "full user list should include permissions"
    return None


def no_permissions(body: object | None) -> str | None:
    if not isinstance(body, list) or not body:
        return "expected a non-empty user option list"
    if "permissions" in body[0]:
        return "user option list must not expose permissions"
    return None


def only_sales_roles(body: object | None) -> str | None:
    if not isinstance(body, list) or not body:
        return "expected a non-empty sales user option list"
    invalid = [
        item.get("username")
        for item in body
        if isinstance(item, dict) and "sales" not in set(item.get("roles") or [])
    ]
    if invalid:
        return f"non-sales users returned: {', '.join(str(item) for item in invalid[:5])}"
    return None


def permissions_are_available(body: object | None) -> str | None:
    if not isinstance(body, list) or not body:
        return "expected a non-empty permission list"
    first = body[0]
    if not isinstance(first, dict):
        return "expected permission objects"
    required = {"id", "code", "name", "type", "sort_no"}
    missing = required - set(first)
    if missing:
        return f"permission object missing fields: {', '.join(sorted(missing))}"
    codes = {item.get("code") for item in body if isinstance(item, dict)}
    for code in ("system:permission", "order:create", "workflow_v2:view"):
        if code not in codes:
            return f"missing expected permission: {code}"
    return None


def product_options_are_minimal(body: object | None) -> str | None:
    if not isinstance(body, list):
        return "expected product option list"
    if not body:
        return None
    first = body[0]
    if not isinstance(first, dict):
        return "expected product option objects"
    forbidden = {"status", "remark"} & set(first)
    if forbidden:
        return f"product options should not include management fields: {', '.join(sorted(forbidden))}"
    required = {"id", "product_code", "name", "unit"}
    missing = required - set(first)
    if missing:
        return f"product option missing fields: {', '.join(sorted(missing))}"
    return None


def main() -> int:
    runner = SmokeRunner()
    try:
        return runner.run()
    finally:
        runner.close()


if __name__ == "__main__":
    sys.exit(main())
