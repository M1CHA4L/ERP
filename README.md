# 制造业 ERP 系统

这是一个面向制版加工企业的 ERP 项目骨架，目标是覆盖：

客户下单 -> 版号/版辊参数 -> 生产通知表 -> 车间任务 -> 派工报工/电雕录入 -> 质检返工 -> 版辊入库/送货 -> 日收入/收据 -> 按版号月结 -> 客户账单/订单归档。

## 当前阶段

已完成第一步工程骨架：

- Docker Compose：PostgreSQL、FastAPI 后端、Vue 3 前端
- 后端分层：API、schemas、models、services、db、core
- 数据模型：客户、订单、产品、工艺路线、工单、工序、报工、质检、返工、送货、财务、文件、日志、RBAC
- RBAC 基础：用户、角色、权限、权限依赖
- 默认种子数据：管理员、角色权限、路线 A、路线 B、基础工序模板
- 核心业务规则骨架：订单确认后生成工单、工单按路线生成工序任务、工序按顺序开始
- 前端基础页面：登录、工作台、客户、订单、工艺路线、生产工单
- 订单到工单闭环：新建订单、订单详情、确认订单、生成工单、工单详情、派工、开始工序、完成报工
- 客户/订单删除：新增客户和未生成工单的订单可删除，采用软删除保留业务安全边界
- 质检返工：待检验工序列表、质检提交、失败返工回到指定工序
- 送货与财务：检验完成后生成送货单、发货、签收、生成应收、登记部分/全额收款
- 成本利润与 Excel：录入成本、查看订单毛利、导出利润报表 `.xlsx`
- 操作日志与多模块导出：关键业务动作写入 `operation_logs`，客户、订单、工单、应收、利润报表支持 Excel 导出
- 生产看板与我的任务：按工序汇总排队、加工中、待检、返工、逾期，操作员可查看并处理自己被派发的工序任务
- 文件附件与现场图片：订单图纸/样品图、工单附件、工序现场照片、质检图片统一上传、下载、软删除并记录操作日志
- 数据库迁移与基础资料：接入 Alembic 第一版迁移，补产品管理、工序模板维护和产品 Excel 导出
- 订单创建体验：新建订单支持多行明细，既可以选择产品模板带出规格、单位、参考价、默认路线，也可以手动填写或覆盖这些字段
- 制版厂功能细则：PRD 已按旧系统截图补充新版/旧版/退镀/返工下单、生产通知表、车间任务单、电雕录入、收据、客户账单、销售月绩、库存入库、领料、版辊入库和客户来料规则
- 版号追踪与打印：新增版号综合查询、制版订单列表、生产通知表 HTML 打印、车间任务单 HTML 打印
- 日收入与月结：新增日收入登记、收款分摊到版号、审核、收据打印、按客户/版号/月度汇总、客户账单生成与打印
- 打印留痕：收据、客户账单、生产通知表、车间任务单每次打印都会写入打印记录，保留数据快照和 HTML 快照，并新增“打印记录”页面
- 财务导出：日收入表、版号月结、客户账单记录支持按当前筛选条件导出 Excel
- 库存与客户来料：新增库存批次、入库单、领料单、客户来料限制、版辊入库单和库存流水
- 前端入口：新增“版号追踪”“库存来料”“日收入月结”页面，并在下单时提示客户已存来料
- 订单类型与电雕录入：下单支持新版、旧版/加做、退镀、返工类型，退镀/返工有专用字段；订单详情支持电雕录入并按颜色记录曲线、网线、角度、深浅、通透、高光和文件保存状态

## 本地启动

1. 创建环境变量文件：

```bash
cp .env.example .env
```

2. 启动服务：

```bash
docker compose up --build
```

3. 初始化数据库和种子数据：

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.db.init_db
```

4. 访问系统：

- 前端：http://localhost:5173
- 后端文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

本地初始化账号：

- 用户名：admin
- 密码：admin123

## 关键 API

- `POST /api/v1/auth/login` 登录
- `GET /api/v1/dashboard/summary` 首页汇总
- `GET/POST /api/v1/customers` 客户列表/新增
- `DELETE /api/v1/customers/{customer_id}` 删除客户
- `GET /api/v1/customers/export` 导出客户 Excel
- `GET/POST /api/v1/products` 产品列表/新增
- `PUT/DELETE /api/v1/products/{product_id}` 编辑/删除产品
- `GET /api/v1/products/export` 导出产品 Excel
- `GET/POST /api/v1/sales-orders` 订单列表/新增
- `POST /api/v1/sales-orders/{order_id}/confirm` 确认订单
- `POST /api/v1/sales-orders/{order_id}/work-orders` 生成生产工单
- `DELETE /api/v1/sales-orders/{order_id}` 删除订单
- `GET /api/v1/sales-orders/export` 导出订单 Excel
- `GET /api/v1/process-routes` 工艺路线
- `GET/POST /api/v1/process-routes/templates` 工序模板列表/新增
- `PUT/DELETE /api/v1/process-routes/templates/{template_id}` 编辑/禁用工序模板
- `GET /api/v1/work-orders` 生产工单
- `GET /api/v1/work-orders/export` 导出工单 Excel
- `GET /api/v1/work-orders/board` 生产工序看板
- `GET /api/v1/work-orders/my-steps` 我的工序任务
- `POST /api/v1/work-orders/{work_order_id}/dispatch` 工序派工
- `POST /api/v1/work-orders/steps/{step_id}/start` 开始工序
- `POST /api/v1/work-orders/steps/{step_id}/complete` 完成工序
- `GET /api/v1/users` 派工人员列表
- `GET /api/v1/inspections/pending` 待检验工序
- `POST /api/v1/inspections/work-order-steps/{step_id}` 提交质检
- `GET /api/v1/delivery-orders/deliverable` 可送货订单
- `POST /api/v1/delivery-orders` 生成送货单
- `POST /api/v1/delivery-orders/{delivery_id}/ship` 发货
- `POST /api/v1/delivery-orders/{delivery_id}/sign` 签收
- `GET /api/v1/finance/receivables` 应收列表
- `GET /api/v1/finance/receivables/export` 导出应收 Excel
- `POST /api/v1/finance/delivery-orders/{delivery_id}/receivable` 生成应收
- `POST /api/v1/finance/receivables/{receivable_id}/payments` 收款登记
- `GET/POST /api/v1/cost-records` 成本列表/录入
- `GET /api/v1/reports/profit` 利润报表
- `GET /api/v1/reports/profit/export` 导出利润报表 Excel
- `GET /api/v1/operation-logs` 查询操作日志
- `GET /api/v1/files` 查询业务附件
- `POST /api/v1/files/upload` 上传业务附件
- `GET /api/v1/files/{file_id}/download` 下载附件
- `DELETE /api/v1/files/{file_id}` 删除附件记录


