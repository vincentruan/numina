# Data Portability Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 数据导入导出，支持备份和迁移

---

## Problem

数据缺乏导入导出功能，用户无法备份资产数据，迁移困难。批量编辑资产需要逐条手动修改，效率低下。系统迁移时缺少全量备份方案。

---

## Goals

1. 支持 CSV 导出便于 Excel 查看、批量编辑
2. 支持 JSON 全量备份和版本管理
3. 支持 CSV 导入批量创建资产
4. 提供清晰错误反馈指导用户修正数据

---

## Architecture

### 导出路径

```
用户点击导出 → 后端生成文件 → 浏览器下载
```

**CSV 导出**：资产/负债单独导出，包含关联数据（分类名称、标签名称）
**JSON 导出**：全量备份，包含 export_version 字段支持未来格式升级

### 导入路径

```
用户上传 CSV → 后端校验 → 逐行处理 → 返回成功/失败结果
```

校验失败时返回具体行号和错误信息，用户可针对性修正。

---

## Implementation Details

### CSV 导出格式

**资产 CSV 字段**

| 字段 | 说明 | 示例 |
|------|------|------|
| id | 资产 ID | uuid |
| name | 资产名称 | MacBook Pro |
| category | 分类名称 | 📱数码 |
| tags | 标签名称（逗号分隔） | 工作,电子 |
| asset_type | 资产类型 | physical/financial |
| purchase_price | 购买价格 | 15000 |
| current_value | 当前价值 | 12000 |
| currency | 币种 | CNY |
| purchase_date | 购买日期 | 2024-01-15 |
| status | 状态 | in_use |

**编码**：UTF-8 with BOM（Excel 兼容）

**实现**

```python
@router.get("/export/assets/csv")
def export_assets_csv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assets = AssetService.list_assets(user.family_id, db)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入 BOM（Excel 兼容）
    output.write('\ufeff')
    
    # 表头
    writer.writerow(["id", "name", "category", "tags", ...])
    
    # 数据行
    for asset in assets:
        writer.writerow([
            asset.id,
            asset.name,
            asset.category.name,
            ",".join(t.name for t in asset.tags),
            ...
        ])
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assets.csv"}
    )
```

### JSON 全量导出

**导出结构**

```json
{
  "export_version": "1.0",
  "exported_at": "2026-04-20T10:30:00Z",
  "family": {
    "name": "Demo Family",
    "invite_code": "ABC123"
  },
  "assets": [...],
  "liabilities": [...],
  "wishes": [...],
  "categories": [...],
  "tags": [...]
}
```

**版本管理**
- `export_version`：当前版本 "1.0"
- 未来格式变更时更新版本号，导入时可识别版本并适配

**实现**

```python
@router.get("/export/all/json")
def export_all_json(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return {
        "export_version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "family": user.family,
        "assets": [AssetSchema.from_orm(a) for a in assets],
        "liabilities": [LiabilitySchema.from_orm(l) for l in liabilities],
        "wishes": [WishSchema.from_orm(w) for w in wishes],
        "categories": [CategorySchema.from_orm(c) for c in categories],
        "tags": [TagSchema.from_orm(t) for t in tags]
    }
```

### CSV 导入校验

**校验规则**

| 字段 | 校验规则 | 错误信息 |
|------|----------|----------|
| name | 必填、不超过100字符 | 第5行：名称不能为空 |
| category | 必填、必须是已存在分类 | 第8行：分类不存在 |
| purchase_price | 必填、必须是数字 | 第10行：购买价格格式错误 |
| currency | 必填、必须是支持的币种 | 第12行：币种不支持 |

**导入流程**

```python
@router.post("/import/assets/csv")
def import_assets_csv(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    success = 0
    failed = 0
    errors = []
    
    content = file.file.read().decode('utf-8-sig')  # 处理 BOM
    reader = csv.DictReader(io.StringIO(content))
    
    for row_num, row in enumerate(reader, start=2):  # 起始行号（跳过表头）
        try:
            # 校验分类
            category = CategoryService.find_by_name(row["category"], db)
            if not category:
                raise ValueError("分类不存在")
            
            # 校验金额
            purchase_price = float(row["purchase_price"])
            
            # 创建资产
            AssetService.create_asset(user.id, category.id, row, db)
            success += 1
            
        except ValueError as e:
            failed += 1
            errors.append({"row": row_num, "message": str(e)})
    
    return {"success": success, "failed": failed, "errors": errors}
```

**导入响应**

```json
{
  "success": 10,
  "failed": 2,
  "errors": [
    {"row": 5, "message": "分类不存在"},
    {"row": 8, "message": "购买价格格式错误"}
  ]
}
```

### 图片上传

**端点**：`POST /upload/image`

**支持格式**：JPEG、PNG、WebP（通过 magic bytes 验证）
**最大大小**：5MB
**存储位置**：`backend/uploads/`

**响应**

```json
{
  "url": "/uploads/abc123.jpg"
}
```

---

## Verification

- 导出资产 CSV 后可在 Excel 正常打开（UTF-8 BOM）
- 导出 JSON 包含 export_version 字段
- 导入正确格式 CSV 返回 success 计数
- 导入错误格式 CSV 返回具体行号和错误信息
- 图片上传返回可访问的 URL

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| CSV 导出 | `backend/app/routers/export.py` |
| JSON 导出 | `backend/app/routers/export.py` |
| CSV 导入 | `backend/app/routers/import_.py` |
| 图片上传 | `backend/app/routers/upload.py` |

---

## Related Specs

- **API规范设计**：`2026-04-20-api-spec-design.md` — /export、/import、/upload 端点
- **文件上传安全**：`2026-04-20-file-upload-security-design.md` — magic bytes 验证