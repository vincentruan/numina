# 3D Things — 3D 物件图标集

7611 张 3D 渲染 PNG/WebP 图标，按 22 个类别分目录组织。

## 目录结构

```
3d-things/
├── 音乐乐器/    (Guitar Amplifier, Karaoke Microphone, ...)
├── 电子设备/    (Smartphone, Laptop, ...)
├── 娱乐休闲/
├── 科学技术/
├── 办公文具/
├── 人物角色/
├── 厨房用品/
├── 历史名人/
├── 交通工具/
├── 植物花卉/
├── 动物生物/
├── 宗教神话/
├── 医疗健康/
├── 建筑地点/
├── 家具家居/
├── 旗帜标志/
├── 工具器械/
├── 数字符号/
├── 食物饮品/
├── 服装配饰/
├── 运动健身/
└── 艺术文化/
```

## 使用方式

直接导入单个文件（Vite `?url` 后缀，返回哈希 URL）：

```ts
import guitarAmp from '@numina/assets/icons/3d-things/音乐乐器/吉他音箱_Guitar Amplifier.png?url'
// <img :src="guitarAmp" />
```

动态加载（Vite glob import）：

```ts
const modules = import.meta.glob('./3d-things/**/*.png', { eager: true, query: '?url', import: 'default' })
// modules['./3d-things/音乐乐器/吉他音箱_Guitar Amplifier.png'] → URL string
```

## 命名约定

文件名格式：`中文名_English Name.ext`（如 `吉他音箱_Guitar Amplifier.png`）
