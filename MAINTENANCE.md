# ERP Maintenance Checks

Run these from `D:\ERP 2`.

## Permission Smoke

```powershell
docker compose exec backend python -m app.tools.permission_smoke
```

Checks key account boundaries for `xiang`, `shohag`, `farhad`, `al_amin`, and `abdul_bari`.

It also checks that `liang`, `rana`, and `shen` keep both `sales` and `production_manager` roles for cross-department manager access.

## Workflow Smoke

```powershell
docker compose exec backend python -m app.tools.workflow_smoke
```

Runs a full workflow v2 path in one transaction and rolls it back by default: test order, workflow start, making dispatch, epin, processing, join, inspection, finance bill, delivery, sign-off, and completion.

To keep the generated smoke order for manual review:

```powershell
docker compose exec backend python -m app.tools.workflow_smoke --commit
```

## Text Smoke

```powershell
docker compose exec backend python -m app.tools.text_smoke
docker compose exec frontend npm run smoke:text
```

Scans backend and frontend source for obvious mojibake or broken labels.

## Build

```powershell
docker compose exec frontend npm run build
```

## Services

```powershell
docker compose ps
```
