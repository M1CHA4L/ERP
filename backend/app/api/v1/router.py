from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    costs,
    customers,
    dashboard,
    delivery_orders,
    finance,
    files,
    inspections,
    inventory,
    operation_logs,
    maintenance,
    plate_numbers,
    plate_orders,
    print_jobs,
    process_routes,
    products,
    sales_orders,
    users,
    workflow_v2,
    work_orders,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(process_routes.router, prefix="/process-routes", tags=["process routes"])
api_router.include_router(sales_orders.router, prefix="/sales-orders", tags=["sales orders"])
api_router.include_router(plate_numbers.router, prefix="/plate-numbers", tags=["plate numbers"])
api_router.include_router(plate_orders.router, prefix="/plate-orders", tags=["plate orders"])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work orders"])
api_router.include_router(workflow_v2.router, prefix="/workflow-v2", tags=["workflow v2"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(inspections.router, prefix="/inspections", tags=["inspections"])
api_router.include_router(delivery_orders.router, prefix="/delivery-orders", tags=["delivery orders"])
api_router.include_router(finance.router, prefix="/finance", tags=["finance"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(costs.router, prefix="", tags=["costs and reports"])
api_router.include_router(operation_logs.router, prefix="/operation-logs", tags=["operation logs"])
api_router.include_router(print_jobs.router, prefix="/print-jobs", tags=["print jobs"])
api_router.include_router(maintenance.router, prefix="/maintenance", tags=["maintenance"])
