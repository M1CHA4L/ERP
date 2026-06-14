from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.permissions import DEFAULT_PERMISSIONS, ROLE_PERMISSION_MAP
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.process import ProcessRoute, ProcessRouteStep, ProcessTemplate
from app.models.rbac import Permission, Role, User
from app.services.workflow_v2 import seed_default_parallel_workflow_template


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

CROSS_DEPARTMENT_MANAGER_USERS = {"liang", "rana", "shen"}


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    with SessionLocal() as db:
        seed_permissions(db)
        seed_roles(db)
        seed_admin_user(db)
        seed_process_templates_and_routes(db)
        seed_default_parallel_workflow_template(db)
        db.commit()


def ensure_schema_updates() -> None:
    inspector = inspect(engine)
    if "customer_statement_runs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("customer_statement_runs")}
    statements: list[str] = []
    if "price_approval_status" not in columns:
        statements.append("ALTER TABLE customer_statement_runs ADD COLUMN price_approval_status VARCHAR(32) NOT NULL DEFAULT 'pending'")
    if "price_approved_at" not in columns:
        statements.append("ALTER TABLE customer_statement_runs ADD COLUMN price_approved_at TIMESTAMP WITH TIME ZONE")
    if "price_approved_by" not in columns:
        statements.append("ALTER TABLE customer_statement_runs ADD COLUMN price_approved_by UUID REFERENCES users(id)")
    if "price_approval_remark" not in columns:
        statements.append("ALTER TABLE customer_statement_runs ADD COLUMN price_approval_remark TEXT")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def seed_permissions(db: Session) -> None:
    existing = {permission.code: permission for permission in db.query(Permission).all()}
    for index, item in enumerate(DEFAULT_PERMISSIONS):
        permission = existing.get(item.code)
        if permission is None:
            db.add(Permission(code=item.code, name=item.name, type=item.type, sort_no=index))
            continue
        permission.name = item.name
        permission.type = item.type
        permission.sort_no = index
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
        ("admin", "admin123", "系统管理员", "管理", ("admin",)),
        ("abdul_bari", "bspm123", "Abdul Bari", "仓库", ("delivery",)),
        ("al_amin", "bspm123", "Al amin", "会计 / 财务部门", ("finance",)),
        ("alamin_sheik", "bspm123", "Alamin Sheik", "基磨床 / Basic Grinding", ("operator",)),
        ("alomgir", "bspm123", "Alomgir", "看样制作 / Proofing production", ("designer",)),
        ("amirul", "bspm123", "Amirul", "看样制作 / Proofing production", ("designer",)),
        ("ariful_islam", "bspm123", "Ariful Islam", "销售员", ("sales",)),
        ("ased_ali", "bspm123", "Ased Ali", "Lathe", ("operator",)),
        ("aslam_hossen", "bspm123", "Aslam Hossen", "设计 / Design", ("designer",)),
        ("ayaz", "bspm123", "Ayaz", "看样制作 / Proofing production", ("designer",)),
        ("babu", "bspm123", "Babu", "制作 / Production", ("designer",)),
        ("bijoymarn", "bspm123", "Bijoymarn", "检验 / Inspection", ("inspector",)),
        ("debash", "bspm123", "Debash", "制作 / Production", ("designer",)),
        ("dhiman", "bspm123", "Dhiman", "电拼 / Carving Make-up", ("operator",)),
        ("emran", "bspm123", "Emran", "雕刻 / Engraving", ("operator",)),
        ("fahim", "bspm123", "Fahim", "设计 / Design", ("designer",)),
        ("farhad", "bspm123", "Farhad", "销售员", ("sales",)),
        ("helal_hossain", "bspm123", "Helal Hossain", "销售员", ("sales",)),
        ("ibrahim", "bspm123", "Ibrahim", "卷板 / Sheet Bending", ("operator",)),
        ("iqbal_hossan", "bspm123", "Iqbal Hossan", "雕刻 / Engraving", ("operator",)),
        ("isnail", "bspm123", "Isnail", "铜磨 / Copper Grinding", ("operator",)),
        ("jony", "bspm123", "Jony", "看样制作 / Proofing production", ("designer",)),
        ("liang", "bspm123", "Liang", "生产 / 销售管理", ("sales", "production_manager")),
        ("md_abul_hasan", "bspm123", "Md.Abul Hasan", "镀铜/镀铬/退铬", ("operator",)),
        ("moniruzaaman", "bspm123", "Moniruzaaman", "销售经理", ("sales",)),
        ("mostofa", "bspm123", "Mostofa", "销售员", ("sales",)),
        ("mujahid", "bspm123", "Mujahid", "设计 / Design", ("designer",)),
        ("mushfik", "bspm123", "Mushfik", "设计 / Design", ("designer",)),
        ("parvej", "bspm123", "Parvej", "制作 / Production", ("designer",)),
        ("rana", "bspm123", "Rana", "生产 / 销售管理", ("sales", "production_manager")),
        ("rasel", "bspm123", "Rasel", "制作 / Production", ("designer",)),
        ("rasel_mia", "bspm123", "Rasel Mia", "机加工", ("operator",)),
        ("rezaul_islam", "bspm123", "Rezaul Islam", "出纳", ("finance",)),
        ("rocky", "bspm123", "Rocky", "基磨床 / Basic Grinding", ("operator",)),
        ("rokan", "bspm123", "Rokan", "销售员", ("sales",)),
        ("rozaio", "bspm123", "Rozaio", "销售员", ("sales",)),
        ("sabbir", "bspm123", "Sabbir", "打样 / Proofing", ("operator",)),
        ("selim_mia", "bspm123", "Selim Mia", "机加工", ("operator",)),
        ("shamim", "bspm123", "Shamim", "销售员", ("sales",)),
        ("shen", "bspm123", "Shen", "生产 / 销售管理", ("sales", "production_manager")),
        ("shipan", "bspm123", "Shipan", "打样 / Proofing", ("operator",)),
        ("shohag", "bspm123", "Shohag", "生产经理 / 生产部门", ("production_manager",)),
        ("shohag_ali", "bspm123", "Shohag Ali", "工厂开票", ("finance",)),
        ("shoriful_islam", "bspm123", "Shoriful Islam", "销售员", ("sales",)),
        ("sobib_mia", "bspm123", "Sobib Mia", "铜磨 / Copper Grinding", ("operator",)),
        ("sobuj_howlader", "bspm123", "Sobuj Howlader", "销售员", ("sales",)),
        ("sumon", "bspm123", "Sumon", "统计", ("finance",)),
        ("suruj_hawlader", "bspm123", "Suruj Hawlader", "卷板 / Sheet Bending", ("operator",)),
        ("xiang", "bspm123", "Xiang", "老板", ("boss", "admin")),
        ("yamin", "bspm123", "Yamin", "镀铜/镀铬/退铬", ("operator",)),
        ("zhang", "bspm123", "Zhang", "生产", ("production_manager",)),
        ("zonaki_akther", "bspm123", "Zonaki Akther", "销售员", ("sales",)),
    ]
    roles = {role.code: role for role in db.query(Role).all()}
    for username, password, real_name, department, role_codes in seed_users:
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
        elif username in CROSS_DEPARTMENT_MANAGER_USERS and (not user.department or user.department == "生产"):
            user.department = department
        desired_roles = [roles[role_code] for role_code in role_codes if role_code in roles]
        if username == "xiang":
            user.roles = desired_roles
        else:
            for role in desired_roles:
                if role not in user.roles:
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
