# 3D 图标目录 — CLAUDE.md

## 目录结构

```
3d-things/
├── animals/             (1017) 动物生物 → 宠物类资产
── art-culture/         (348)  艺术文化 → 奢侈品/收藏
── buildings/           (508)  建筑地点 → 房产类资产
├── clothing-accessories/(516)  服装配饰 → 服饰/珠宝/箱包
├── electronics/         (345)  电子设备 → 数码类资产
├── entertainment/       (296)  娱乐休闲 → 玩具类资产
├── furniture/           (314)  家具家居 → 家具/家电
── healthcare/          (256)  医疗健康 → 其他（医疗器械）
── instruments/         (120)  音乐乐器 → 乐器类资产
├── kitchenware/         (230)  厨房用品 → 家电（厨房电器）
├── office-stationery/   (207)  办公文具 → 其他
├── plants/              (303)  植物花卉 → 其他（珍稀植物）
├── science-tech/        (293)  科学技术 → 数码（实验设备）
├── sports/              (413)  运动健身 → 运动类资产
├── tools/               (450)  工具器械 → 其他（工具）
└── vehicles/            (405)  交通工具 → 车辆类资产
```

**总计：** 16 分类，6021 图标，~447MB

## 缩略图管道

### 生成命令

```bash
# 从 repo 根目录运行
cd frontend/apps/main
pnpm generate:thumbs
```

### 规格

| 参数 | 值 |
|------|-----|
| 尺寸 | 256×256 px |
| 格式 | WebP |
| 质量 | 90 |
| 输出 | `public/icons/3d-thumbs/{category}/{name}.webp` |
| 总大小 | ~140MB（6021 张） |

### 增量生成

脚本跳过已存在的缩略图。添加新图标后重新运行即可。

### 原始图

```
public/icons/3d/{category}/{name}.png|webp
```

原始图通过 `deploy-icons.ts` 脚本以符号链接方式从本目录复制到 `public/icons/3d/`。

## 分类映射

### 系统资产分类 → 3D 图标分类

| 系统分类 | 3D 图标分类 | 说明 |
|---------|------------|------|
| 房产 | buildings | 房屋、公寓、别墅 |
| 车辆 | vehicles | 汽车、卡车、飞机 |
| 数码 | electronics, science-tech | 手机、电脑、实验设备 |
| 家电 | furniture, kitchenware | 家具、厨房电器 |
| 珠宝 | clothing-accessories | 首饰、配饰 |
| 服饰 | clothing-accessories | 服装、箱包 |
| 美妆 | clothing-accessories | 化妆品、香水 |
| 运动 | sports | 运动器材 |
| 玩具 | entertainment | 玩具、游戏 |
| 宠物 | animals | 猫、狗、鱼、鸟 |
| 乐器 | instruments | 钢琴、吉他、鼓 |
| 箱包 | clothing-accessories | 手提包、行李箱 |
| 奢侈品 | art-culture, clothing-accessories | 艺术品、收藏品 |

### 命名约定

- **文件夹：** 英文 kebab-case（如 `clothing-accessories`）
- **文件名：** `中文名_English Name.ext`（如 `吉他音箱_Guitar Amplifier.png`）
- **缩略图：** `中文名_English Name.webp`（同名，扩展名改为 .webp）

## Manifest 生成

```bash
cd frontend/apps/main
pnpm deploy:icons   # 先部署符号链接
# 然后手动运行（暂无 npm script）
npx tsx scripts/build-icon-manifest.ts
```

生成 `frontend/packages/assets/src/icons/icon-manifest.ts`，包含：
- 16 个分类定义（id, nameZh, nameEn, folder, sortOrder, assetCategoryHints）
- 6021 个图标条目（fileName, nameZh, nameEn）

## 关键决策

### KTD-1: TypeScript manifest（非 CSV）

类型安全，IDE 自动补全，Vite tree-shaking。

### KTD-2: public 目录 serve（非 import）

6021 个文件的 import 会创建数千个 Vite 模块。public 目录文件不进入 JS bundle，URL 引用天然支持懒加载。

### KTD-3: 256px 缩略图

- 128px 太小，详情页不够清晰
- 256px 在移动端详情页（~200px 显示尺寸）足够清晰
- 单张 ~20KB，总 ~140MB，可接受

### KTD-4: 3D 图标无水印

预设资源，非用户创作，无需水印保护。

## 维护

### 添加新图标

1. 将文件放入对应分类文件夹（遵循 `中文名_English Name.ext` 命名）
2. 运行 `pnpm generate:thumbs` 生成缩略图
3. 运行 `npx tsx scripts/build-icon-manifest.ts` 更新 manifest
4. 提交到 git（通过 Git LFS）

### 添加新分类

1. 创建英文 kebab-case 文件夹
2. 更新 `scripts/deploy-icons.ts` 的 `CATEGORIES` 数组
3. 更新 `scripts/build-icon-manifest.ts` 的 `CATEGORY_DEFS` 数组
4. 更新 `frontend/packages/assets/package.json` 的 `exports` 字段
5. 运行 deploy + generate + build 脚本
6. 更新本 CLAUDE.md 的目录结构

### 删除分类

反向操作上述步骤。注意检查是否有资产引用该分类的图标。

## Git LFS

所有 PNG/WebP 文件通过 Git LFS 追踪（`.gitattributes` 已配置）。

```bash
# 查看 LFS 状态
git lfs ls-files | wc -l

# 拉取 LFS 文件
git lfs pull
```
