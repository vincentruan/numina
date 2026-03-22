# Numina 项目恢复指南

## 当前状态（2024-03-22）

### ✅ 已完成功能
1. **导航修复** - AppTabBar 状态管理修复，6个tab（首页、心愿、+、负债、统计、设置）
2. **数据刷新** - 资产操作后自动刷新
3. **多视图工具栏** - 排序（10种）、筛选（标签）、选择（批量操作）
4. **分类视图** - 按分类分组展示 + 滚动吸顶导航栏
5. **分享功能** - 单个/多个资产卡片生成（html2canvas）

### 📋 待完成任务（按优先级）

#### Phase 3: 心愿功能
- [ ] #1 产品需求验证
- [ ] #2 后端实现（Wish模型、API、转化为资产）
- [ ] #3 前端实现（列表、表单、详情页）

#### Phase 4: 批量操作
- [ ] #4 后端API（删除、分类、标签、状态变更、导出）
- [ ] #5 前端集成（DashboardPage）

#### Phase 5: 其他功能
- [ ] #6 日均分摊曲线图（AssetDetailPage）
- [ ] #7 数据统计页面（DataStatsPage）
- [ ] #8 设置后端（User模型扩展、数据管理API）
- [ ] #9 设置前端（主题、语言、币种、视图模式）
- [ ] #10 汇率系统（ExchangeRate模型、定时任务）
- [ ] #11 资产录入表单优化（上下两部分布局）

#### Phase 6: 测试验收
- [ ] #12 第二批功能测试（分享+分类）
- [ ] #13 全面回归测试和产品验收

### 🎯 团队配置
- **Team**: numina-completion
- **成员**: 产品经理、后端开发、前端开发、测试

### 📁 关键文件位置

**已修改的核心文件**:
- `frontend/src/components/common/AppTabBar.vue` - 修复状态管理
- `frontend/src/pages/DashboardPage.vue` - 多视图+工具栏+分类+分享
- `frontend/src/pages/AssetFormPage.vue` - 数据刷新修复
- `frontend/src/composables/useViewMode.ts` - 视图模式管理
- `frontend/src/utils/shareImage.ts` - 分享功能

**参考文档**:
- `docs/implementation-status.md` - 完整实施状态
- `docs/current-status.md` - 快速参考
- `.claude/plans/bright-fluttering-parrot.md` - 产品优化计划
- `docs/images/references/` - 13张参考截图

### 🔧 技术栈
- **前端**: Vue 3 + TypeScript + Vant 4 + Pinia + ECharts + html2canvas
- **后端**: Python + FastAPI + SQLAlchemy + APScheduler
- **部署**: Docker + nginx（子路径 /numina/）

### 📊 验收标准
1. 所有参考截图功能都已实现
2. 交互流程连贯、符合产品逻辑
3. Chrome DevTools 测试通过（375x812 viewport）
4. 视觉还原度 > 90%
5. 无明显 bug 和性能问题

### 🚀 快速启动命令

**查看任务**:
```
TaskList
```

**查看团队状态**:
```bash
cat ~/.claude/teams/numina-completion/config.json
```

**启动开发**:
```bash
# 前端
cd frontend && npm run dev

# 后端
cd backend && uv run uvicorn app.main:app --reload
```

**运行测试**:
```bash
# 前端类型检查
cd frontend && npx vue-tsc -b --noEmit

# 前端构建
cd frontend && npm run build

# 后端测试
cd backend && uv run pytest tests/ -v
```

### 💡 重要提示
1. 所有任务已创建在 TaskList 中
2. 团队成员会自动处理任务
3. 每完成一批功能立即测试验证
4. 根据测试反馈持续迭代优化
5. 最终目标：对标"有数App"，完成所有参考截图功能

### 📞 下一步行动
1. 使用 `TaskList` 查看所有待办任务
2. 团队成员开始并行开发
3. 产品经理验证需求（任务 #1）
4. 后端开发实现心愿功能（任务 #2）
5. 前端开发实现心愿界面（任务 #3）
6. 持续推进直到所有任务完成

---

**最后更新**: 2024-03-22
**项目状态**: Phase 1-2 完成，Phase 3-6 进行中
**团队**: numina-completion (4人)
**任务数**: 13个待完成
