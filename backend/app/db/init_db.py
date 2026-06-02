from sqlalchemy.orm import Session

from app.core.permissions import DEFAULT_PERMISSIONS, ROLE_PERMISSION_MAP
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.process import ProcessRoute, ProcessRouteStep, ProcessTemplate
from app.models.rbac import Permission, Role, User


PROCESS_DEFINITIONS = [
    ("P001", "机械加工", "加工", False),
    ("P002", "卷板", "加工", False),
    ("P003", "车床", "加工", False),
    ("P004", "磨床", "加工", False),
    ("P005", "镀铜", "加工", False),
    ("P006", "研磨", "加工", False),
    ("P007", "雕刻", "加工", False),
    ("P014", "电雕", "加工", False),
    ("P008", "镀铬", "加工", False),
    ("P009", "打样", "加工", True),
    ("P010", "检验", "检验", True),
    ("P011", "看样/设计", "设计", False),
    ("P012", "排版", "设计", False),
    ("P013", "拼板", "设计", False),
]

ROUTE_DEFINITIONS = [
    (
        "RA",
        "路线 A",
        "机械加工、卷板、车床、磨床、镀铜、研磨、雕刻、镀铬、打样、检验",
        ["机械加工", "卷板", "车床", "磨床", "镀铜", "研磨", "雕刻", "镀铬", "打样", "检验"],
    ),
    (
        "RB",
        "路线 B",
        "看样/设计、排版、拼板、雕刻、镀铬、打样、检验",
        ["看样/设计", "排版", "拼板", "雕刻", "镀铬", "打样", "检验"],
    ),
]

ROLE_NAMES = {
    "admin": "老板/管理员",
    "boss": "老板",
    "sales": "销售/跟单",
    "designer": "设计人员",
    "production_manager": "生产主管",
    "operator": "工序操作员",
    "inspector": "质检员",
    "delivery": "仓库/送货人员",
    "finance": "财务人员",
}


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_permissions(db)
        seed_roles(db)
        seed_admin_user(db)
        seed_process_templates_and_routes(db)
        db.commit()


def seed_permissions(db: Session) -> None:
    existing = {permission.code for permission in db.query(Permission).all()}
    for index, item in enumerate(DEFAULT_PERMISSIONS):
        if item.code not in existing:
            db.add(Permission(code=item.code, name=item.name, type=item.type, sort_no=index))
    db.flush()


def seed_roles(db: Session) -> None:
    permissions = {permission.code: permission for permission in db.query(Permission).all()}
    existing_roles = {role.code: role for role in db.query(Role).all()}
    for role_code, permission_codes in ROLE_PERMISSION_MAP.items():
        role = existing_roles.get(role_code)
        if role is None:
            role = Role(code=role_code, name=ROLE_NAMES.get(role_code, role_code), status="active", is_system=True)
            db.add(role)
            db.flush()
        role.permissions = [permissions[code] for code in permission_codes if code in permissions]


def seed_admin_user(db: Session) -> None:
    seed_users = [
        ("admin", "admin123", "系统管理员", "管理", "admin"),
        ("boss01", "admin123", "老板账号", "管理", "boss"),
        ("design01", "admin123", "设计人员", "设计部", "designer"),
        ("pm01", "admin123", "生产主管", "生产部", "production_manager"),
        ("op01", "admin123", "雕刻操作员", "生产部", "operator"),
        ("op02", "admin123", "镀铬操作员", "生产部", "operator"),
        ("qc01", "admin123", "质检员", "质量部", "inspector"),
        ("sales01", "admin123", "销售跟单", "销售部", "sales"),
        ("delivery01", "admin123", "送货人员", "仓储物流", "delivery"),
        ("finance01", "admin123", "财务人员", "财务部", "finance"),
    ]
    roles = {role.code: role for role in db.query(Role).all()}
    for username, password, real_name, department, role_code in seed_users:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(
                username=username,
                password_hash=get_password_hash(password),
                real_name=real_name,
                department=department,
                status="active",
            )
            db.add(user)
            db.flush()
        role = roles.get(role_code)
        if role and role not in user.roles:
            user.roles.append(role)


def seed_process_templates_and_routes(db: Session) -> None:
    templates_by_code = {template.code: template for template in db.query(ProcessTemplate).all()}
    templates_by_name = {template.name: template for template in templates_by_code.values()}
    for code, name, category, requires_inspection in PROCESS_DEFINITIONS:
        template = templates_by_code.get(code)
        if template is None:
            template = ProcessTemplate(
                code=code,
                name=name,
                category=category,
                requires_inspection=requires_inspection,
                enabled=True,
            )
            db.add(template)
            templates_by_code[code] = template
        else:
            template.name = name
            template.category = category
            template.requires_inspection = requires_inspection
            template.enabled = True
        templates_by_name[name] = template
    db.flush()

    existing_routes = {route.route_code: route for route in db.query(ProcessRoute).all()}
    for route_code, route_name, description, step_names in ROUTE_DEFINITIONS:
        if route_code in existing_routes:
            continue
        route = ProcessRoute(
            route_code=route_code,
            name=route_name,
            description=description,
            version=1,
            is_default=True,
            status="active",
        )
        db.add(route)
        db.flush()
        for index, step_name in enumerate(step_names, start=1):
            template = templates_by_name[step_name]
            db.add(
                ProcessRouteStep(
                    route_id=route.id,
                    process_template_id=template.id,
                    step_no=index,
                    step_name=template.name,
                    is_optional=False,
                    requires_inspection=template.requires_inspection,
                )
            )


if __name__ == "__main__":
    init_db()
