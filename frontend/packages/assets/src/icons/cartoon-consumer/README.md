# 消费卡通 — Consumer Cartoon 图标集

消费场景相关的卡通风格图标。

## 使用方式

直接导入单个文件（Vite `?url` 后缀，返回哈希 URL）：

```ts
import shoppingBag from '@numina/assets/icons/cartoon-consumer/xxx.png?url'
// <img :src="shoppingBag" />
```

动态加载（Vite glob import）：

```ts
const modules = import.meta.glob('./cartoon-consumer/**/*.png', { eager: true, query: '?url', import: 'default' })
```

## 命名约定

文件名格式：`中文名_English Name.ext`（如 `购物袋_Shopping Bag.png`）
