"""System bootstrap — one-time initialization of data required for the system to run.

Unlike Alembic migrations (which handle schema changes), bootstrap ensures that
essential runtime data exists: system categories, currencies, builtin agents,
builtin skills, invitation codes, storage backends, etc.

All bootstrap functions are idempotent — safe to run on every startup.
They use SQLAlchemy ORM for PostgreSQL + SQLite compatibility.
"""

from sqlalchemy.orm import Session

from apps.backend.app.core.logging_config import get_logger

logger = get_logger(__name__)


def run_bootstrap(db: Session) -> None:
    """Execute all system bootstrap steps in dependency order."""
    from apps.backend.app.bootstrap.agents import bootstrap_agents
    from apps.backend.app.bootstrap.categories import bootstrap_categories
    from apps.backend.app.bootstrap.category_financial_defaults import (
        bootstrap_category_financial_defaults,
    )
    from apps.backend.app.bootstrap.currencies import bootstrap_currencies
    from apps.backend.app.bootstrap.family_mcp_servers import (
        bootstrap_family_mcp_servers,
    )
    from apps.backend.app.bootstrap.invitation_codes import bootstrap_invitation_codes
    from apps.backend.app.bootstrap.learning_topics import bootstrap_learning_topics
    from apps.backend.app.bootstrap.skills import bootstrap_skills
    from apps.backend.app.seed.expense_categories import (
        bootstrap_expense_categories,
    )

    # ── 1. 资产/负债分类 ──────────────────────────────────────────
    # 21 个系统预设分类（房产、车辆、数码…），is_system=True 不可删除。
    # 从 YAML 配置 + 硬编码身份列表加载，用于资产/负债录入时的分类选项。
    bootstrap_categories(db)

    # ── 2. 常用货币 ───────────────────────────────────────────────
    # 预置 CNY/USD/EUR/JPY 等常用币种及符号、排序。
    # 资产/负债支持多币种录入，汇率通过 /currencies 接口获取。
    bootstrap_currencies(db)

    # ── 3. 初始邀请码 ─────────────────────────────────────────────
    # 生产环境从 INIT_INVITATION_CODES 环境变量生成；非生产环境额外
    # 注入 CI0001-CI0010 固定码供 E2E 测试使用。
    # 新用户通过邀请码注册家庭，是系统注册的入口凭证。
    bootstrap_invitation_codes(db)

    # ── 4. 分类财务默认参数 ───────────────────────────────────────
    # 为实物类分类预设折旧率、增值率、使用年限等默认值，
    # 例如：车辆年折旧 15%、房产年增值 3%、使用年限 50 年。
    # 录入资产时自动填充，用户可手动覆盖。
    bootstrap_category_financial_defaults(db)

    # ── 5. 内置 AI Agent ──────────────────────────────────────────
    # 注册系统级 Agent（family_id=0）：numina（主对话）、asset-report
    # （资产报告）、finance-coach（财务教练）、import-parse（导入解析）、
    # wish-advice（心愿建议）、learning-tutor（学习辅导）等。
    # 前端 Agent 选择器展示这些系统 Agent 供用户使用。
    bootstrap_agents(db)

    # ── 6. 内置 Skill 模板 ────────────────────────────────────────
    # 预留的系统级 Skill 注册点。当前 asset-report/chat 等已迁移为
    # agent 端文件系统 Skill（由 skill scanner 运行时加载），此处
    # 保留为幂等空操作，确保引导流程完整且未来可扩展。
    bootstrap_skills(db)

    # ── 7. 家庭 MCP Server 记录 ───────────────────────────────────
    # 确保每个家庭都有一条 FamilyMCPServer 行，使 AI Agent 能通过
    # SSE 端点访问 Backend 的内部 MCP 工具（如查询资产、操作标签）。
    # 正常在注册时创建，此引导补齐历史遗留家庭的缺失记录。
    bootstrap_family_mcp_servers(db)

    # ── 8. 旅行模块支出分类 ──────────────────────────────────────
    # 预置旅行场景下的支出分类（餐饮/交通/住宿/活动/购物/杂项），
    # 供旅行预算与记账功能使用。
    bootstrap_expense_categories(db)

    # ── 9. 学习知识图谱主题 ──────────────────────────────────────
    # 从 os-taxonomy 加载学课主题、前置依赖关系、聚类分组。
    # 必须在 main.py 中的题目自动种子（question auto-seed）之前执行，
    # 因为题目的 topic_key → topic_id 映射依赖已存在的主题记录。
    bootstrap_learning_topics(db)

    logger.info("系统初始化数据检查完成")
