# 3D Things — 3D 物件图标集

3296 张 3D 渲染 PNG/WebP 图标，按 10 个资产相关类别分目录组织。

## 目录结构

```
3d-things/
├── vehicles/           (交通工具 — Cars, Trucks, Airplanes, ...)
├── electronics/        (电子设备 — Smartphones, Laptops, ...)
├── furniture/          (家具家居 — Sofas, Tables, Lamps, ...)
├── clothing-accessories/ (服装配饰 — Shoes, Bags, Watches, ...)
├── tools/              (工具器械 — Drills, Wrenches, Saws, ...)
├── sports/             (运动健身 — Balls, Gym Equipment, ...)
├── kitchenware/        (厨房用品 — Pots, Pans, Utensils, ...)
├── entertainment/      (娱乐休闲 — Games, Toys, ...)
├── instruments/        (音乐乐器 — Guitars, Pianos, Drums, ...)
└── office-stationery/  (办公文具 — Printers, Desks, Pens, ...)
```

## 使用方式

直接导入单个文件（Vite `?url` 后缀，返回哈希 URL）：

```ts
import carIcon from '@numina/assets/icons/3d-things/vehicles/ADT卡车_ADT Truck.png?url'
// <img :src="carIcon" />
```

动态加载（Vite glob import）：

```ts
const modules = import.meta.glob('./3d-things/vehicles/**/*.png', { eager: true, query: '?url', import: 'default' })
// modules['./3d-things/vehicles/ADT卡车_ADT Truck.png'] → URL string
```

## 命名约定

文件名格式：`中文名_English Name.ext`（如 `ADT卡车_ADT Truck.png`）

## 来源

原始素材库包含 22 个分类（7612 文件，572MB）。已精简为 10 个资产相关分类（3296 文件，240MB），删除了食物饮品、动物生物、人物角色等非资产相关内容。
