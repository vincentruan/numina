"""add literacy badge system (scenarios, badges, weekly reports)

Revision ID: l1t2e3r4a5c6
Revises: 5c29147d17e4
Create Date: 2026-07-28
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l1t2e3r4a5c6"
down_revision: str | None = "5c29147d17e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Badge definition seeds: 4 dimensions × 3 levels
BADGE_SEEDS = [
    # 赚钱 (earning)
    ("earning", 1, "小帮手", "通过劳动赚取了第一颗星币", "完成至少1个家务任务并获得星币奖励"),
    ("earning", 2, "勤劳小达人", "连续完成家务，理解劳动创造持续价值", "连续7天完成家务，理解坚持的意义"),
    ("earning", 3, "理财小能手", "主动寻找赚取星币的机会，理解劳动的长期价值", "连续14天完成家务+主动提出额外任务"),
    # 选择 (choosing)
    ("choosing", 1, "小决策家", "开始理解每个选择都有代价", "使用过至少1次机会成本对比功能"),
    ("choosing", 2, "机会成本侦探", "在做选择前会主动比较不同选项", "使用机会成本对比2次以上+做出跨愿望选择"),
    ("choosing", 3, "选择力大师", "能够权衡利弊做出最优决策", "多次跨愿望比较+在情境游戏中做出理性选择"),
    # 等待 (waiting)
    ("waiting", 1, "耐心小种子", "开始学习等待的价值", "设置过至少1个心愿并等待攒星币"),
    ("waiting", 2, "延迟满足小达人", "能够为了更大的目标而等待", "坚持攒星币2周以上+不冲动消费"),
    ("waiting", 3, "延迟满足大师", "深刻理解等待带来更大回报", "连续4周坚持储蓄目标+在情境游戏中选择等待"),
    # 关心 (caring)
    ("caring", 1, "小帮手", "开始关心家庭的财务状况", "参与过1次家庭财务讨论或选择分享星币"),
    ("caring", 2, "家庭小管家", "主动参与家庭财务活动", "参与家庭财务活动2次以上+主动分享"),
    ("caring", 3, "家庭财务小顾问", "深刻理解家庭财务协作的价值", "持续参与家庭财务讨论+在情境游戏中展示关心家人的选择"),
]


def upgrade() -> None:
    bind = op.get_bind()

    # Helper: check if table exists (fresh-DB guard)
    def _has_table(name: str) -> bool:
        return bind.dialect.has_table(bind, name)

    def _has_column(table: str, col: str) -> bool:
        if not _has_table(table):
            return False
        cols = {c["name"] for c in bind.dialect.get_columns(bind, table)}
        return col in cols

    # 1. literacy_badge_definitions
    if not _has_table("literacy_badge_definitions"):
        op.create_table(
            "literacy_badge_definitions",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("dimension", sa.String(20), nullable=False),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("criteria_summary", sa.Text(), nullable=False, comment="Short description for AI evaluation context"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dimension", "level", name="uq_badge_def_dimension_level"),
        )
        op.create_index("ix_literacy_badge_definitions_dimension", "literacy_badge_definitions", ["dimension"], unique=False)

    # Seed badge definitions (idempotent)
    existing_count = sa.text("SELECT COUNT(*) FROM literacy_badge_definitions")
    result = bind.execute(existing_count)
    count = result.scalar() if result else 0
    if count == 0:
        for idx, (dim, lvl, name, desc, criteria) in enumerate(BADGE_SEEDS):
            bind.execute(
                sa.text(
                    "INSERT INTO literacy_badge_definitions (id, dimension, level, name, description, criteria_summary) "
                    "VALUES (:id, :dim, :lvl, :name, :desc, :criteria)"
                ),
                {"id": 1000001 + idx, "dim": dim, "lvl": lvl, "name": name, "desc": desc, "criteria": criteria},
            )

    # Scenario template seeds: 4 dimensions × 3 age groups = 12 templates
    TEMPLATE_SEEDS = [
        # ── earning (赚钱) ──────────────────────────────────────────────
        (
            "earning",
            "low",
            "小明今天帮妈妈做了一件事，得到了一些星币⭐。你觉得小明做了什么？",
            json.dumps(
                [
                    {"text": "帮妈妈扫地 🧹", "feedback": "扫地是让家里变干净的劳动，值得奖励！", "dimension_signal": "earning"},
                    {"text": "整理自己的玩具 🧸", "feedback": "整理好自己的东西也是一种负责任的表现！", "dimension_signal": "earning"},
                    {"text": "帮妈妈拿东西 🛍️", "feedback": "帮助家人是一种很好的赚钱方式！", "dimension_signal": "earning"},
                ],
                ensure_ascii=False,
            ),
        ),
        (
            "earning",
            "mid",
            "这周你有机会通过额外的努力赚取星币。你会选择？",
            json.dumps(
                [
                    {"text": "每天多做1个简单任务（5天×2⭐=10⭐）", "feedback": "稳定的小努力可以积累成不小的收获！", "dimension_signal": "earning"},
                    {"text": "周末做一个大任务（一次赚8⭐）", "feedback": "集中时间做大事效率很高，但别忘了持续性也很重要。", "dimension_signal": "earning"},
                    {"text": "这周先休息，下周再赚", "feedback": "偶尔休息没问题，但延迟开始也会延迟目标的达成哦。", "dimension_signal": "earning"},
                ],
                ensure_ascii=False,
            ),
        ),
        (
            "earning",
            "high",
            "你有两个周末可以赚取星币：帮邻居整理花园(100⭐,3小时) 或教弟弟妹妹做题(60⭐,1小时)。但你还想攒钱买一个200⭐的东西。",
            json.dumps(
                [
                    {"text": "两个周末都整理花园(200⭐,6小时)", "feedback": "最大化收入！虽然辛苦但能最快达成目标。", "dimension_signal": "earning"},
                    {"text": "两个周末都教题(120⭐,2小时)", "feedback": "轻松一些，但需要更多周才能攒够200⭐。", "dimension_signal": "earning"},
                    {"text": "第一个周末整理花园，第二个教题(160⭐,4小时)", "feedback": "平衡策略：先快速接近目标，再轻松一些。", "dimension_signal": "earning"},
                ],
                ensure_ascii=False,
            ),
        ),
        # ── choosing (选择) ─────────────────────────────────────────────
        (
            "choosing",
            "low",
            "小熊有5颗星币，它看到🍎苹果玩具(3星币)和🧸小熊玩偶(5星币)。它只能买一个！",
            json.dumps(
                [
                    {"text": "买🍎苹果玩具(3⭐)，还剩2⭐", "feedback": "买了便宜的还能存下一些，不过小熊玩偶就买不了啦。", "dimension_signal": "choosing"},
                    {"text": "买🧸小熊玩偶(5⭐)，星币用完", "feedback": "得到了最喜欢的，但星币就花光啦！", "dimension_signal": "choosing"},
                    {"text": "都不买，继续攒星币", "feedback": "耐心等待可以买到更好的东西哦！", "dimension_signal": "choosing"},
                ],
                ensure_ascii=False,
            ),
        ),
        (
            "choosing",
            "mid",
            "你有30颗星币，可以现在买一个小玩具(15⭐)，或者再等两周(每周赚10⭐)买一个大玩具(40⭐)。",
            json.dumps(
                [
                    {"text": "现在买小玩具(15⭐)，剩15⭐", "feedback": "马上得到了满足，但大玩具就还要再等更久了。", "dimension_signal": "choosing"},
                    {"text": "等两周买大玩具(40⭐)", "feedback": "延迟满足需要耐心，但最终获得的东西更值得！", "dimension_signal": "choosing"},
                    {"text": "先买小玩具，两周后再说", "feedback": "注意：小玩具花了15⭐，两周后只有20⭐+15⭐=35⭐，还不够大玩具呢。", "dimension_signal": "choosing"},
                ],
                ensure_ascii=False,
            ),
        ),
        (
            "choosing",
            "high",
            "你有50颗星币。现在有一个限时打折的文具套装(35⭐)，但你已经攒了3周准备买一个80⭐的拼图。如果现在买文具，拼图还要再攒多久？（每周赚15⭐）",
            json.dumps(
                [
                    {"text": "买文具套装(35⭐)，剩15⭐", "feedback": "文具买了还剩15⭐，拼图还需(80-15)/15≈5周。机会成本：额外多等了约2周。", "dimension_signal": "choosing"},
                    {"text": "不买文具，继续攒拼图", "feedback": "再攒2周就够80⭐了！忍住诱惑是延迟满足的关键。", "dimension_signal": "choosing"},
                    {"text": "再想想，文具是不是真的需要", "feedback": "好问题！买东西前问自己「我真的需要吗？」可以避免冲动消费。", "dimension_signal": "choosing"},
                ],
                ensure_ascii=False,
            ),
        ),
        # ── waiting (等待) ──────────────────────────────────────────────
        (
            "waiting",
            "low",
            "小兔子有3颗星币，它想要一个大蛋糕🎂(8星币)。它应该怎么办？",
            json.dumps(
                [
                    {"text": "每天帮妈妈做事赚1⭐，等5天", "feedback": "耐心等待5天就能吃到大蛋糕啦！🎉", "dimension_signal": "waiting"},
                    {"text": "先买个小饼干(3⭐)解馋", "feedback": "小饼干可以吃，但大蛋糕就还要等更久哦。", "dimension_signal": "waiting"},
                    {"text": "找好朋友一起攒，更快！", "feedback": "和朋友一起努力可以让目标更快实现！", "dimension_signal": "waiting"},
                ],
                ensure_ascii=False,
            ),
        ),
        (
            "waiting",
            "mid",
            "你看到一个你喜欢的东西(20⭐)，你现在有15⭐。每天做2个任务可以赚4⭐。",
            json.dumps(
                [
                    {"text": "再做2天任务就够了(还需5⭐≈2天)", "feedback": "只差2天了！坚持一下就能买到，延迟满足的感觉很棒。", "dimension_signal": "waiting"},
                    {"text": "现在找家人借5⭐", "feedback": "借了就要还，意味着未来几天要做额外任务。有时候等待比借更好。", "dimension_signal": "waiting"},
                    {"text": "放弃这个，换一个更便宜的(15⭐)", "feedback": "降低目标也是一种选择，但想想你是不是真的更喜欢原来那个。", "dimension_signal": "waiting"},
                ],
                ensure_ascii=False,
            ),
        ),
        (
            "waiting",
            "high",
            "你有60⭐。一个限时商品45⭐今天截止，但你正在攒150⭐买一个你真正想要的东西。如果你买了限时商品，你之前6周的积累就白费了吗？（每周赚15⭐）",
            json.dumps(
                [
                    {"text": "买限时商品(45⭐)，剩15⭐", "feedback": "之前6周攒了60⭐不算白费，但还需(150-15)/15=9周！从原来6周变成9周了。", "dimension_signal": "waiting"},
                    {"text": "忍住不买，继续攒150⭐目标", "feedback": "限时感往往是冲动的陷阱。真正想要的东西值得等待，目标只差6周了！", "dimension_signal": "waiting"},
                    {"text": "买限时商品，但下周开始多做一个任务", "feedback": "积极弥补！如果每周多赚5⭐，需要(150-15)/20≈7周，比不弥补好一些。", "dimension_signal": "waiting"},
                ],
                ensure_ascii=False,
            ),
        ),
        # ── caring (关心) ───────────────────────────────────────────────
        (
            "caring",
            "low",
            "姐姐只有2颗星币，但她很想要一个贴纸🌟(5⭐)。你有10颗星币，你会？",
            json.dumps(
                [
                    {"text": "给姐姐3⭐，帮她买贴纸", "feedback": "分享让姐姐开心，你还有7⭐，真棒！❤️", "dimension_signal": "caring"},
                    {"text": "教姐姐怎么赚星币", "feedback": "授人以鱼不如授人以渔！教姐姐赚钱的方法更好。", "dimension_signal": "caring"},
                    {"text": "自己的星币自己留着", "feedback": "保护好自己的星币也没错，但下次可以想想怎么帮助家人。", "dimension_signal": "caring"},
                ],
                ensure_ascii=False,
            ),
        ),
        (
            "caring",
            "mid",
            "家里需要买一个新的日历📅(15⭐)，但如果你贡献10⭐，你自己的攒钱计划就会慢下来。",
            json.dumps(
                [
                    {"text": "贡献10⭐买日历", "feedback": "家庭用品大家一起承担是好的！你的计划只是慢一点，并没有失败。", "dimension_signal": "caring"},
                    {"text": "贡献5⭐，让其他人也出一些", "feedback": "合理的分担方式！每个人出一部分，公平又不会太影响自己。", "dimension_signal": "caring"},
                    {"text": "这次不贡献，下次再说", "feedback": "偶尔不贡献没问题，但家庭共同责任需要大家一起承担。", "dimension_signal": "caring"},
                ],
                ensure_ascii=False,
            ),
        ),
        (
            "caring",
            "high",
            "家庭有一个共同目标：攒500⭐全家去旅行。你现在有80⭐。如果全家每周需要每人贡献20⭐，你愿意把你攒了4周的星币投入家庭目标吗？",
            json.dumps(
                [
                    {"text": "愿意！全家旅行比个人目标更有意义", "feedback": "家庭目标需要每个人的贡献。你的80⭐足够4周的贡献，旅行回忆是无价的。", "dimension_signal": "caring"},
                    {"text": "愿意，但希望每周只贡献10⭐", "feedback": "坦诚沟通你的想法很好！和家人商量一个你能承受的额度。", "dimension_signal": "caring"},
                    {"text": "想先保留，看看个人目标能不能兼顾", "feedback": "合理考虑。但500⭐÷全家人数=每人约125-165⭐，你的80⭐是重要的一部分。", "dimension_signal": "caring"},
                ],
                ensure_ascii=False,
            ),
        ),
    ]

    # 2. literacy_badges
    if not _has_table("literacy_badges"):
        op.create_table(
            "literacy_badges",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("definition_id", sa.BigInteger(), nullable=False),
            sa.Column("earned_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("superseded_at", sa.DateTime(), nullable=True),
            sa.Column("source", sa.String(30), nullable=False, comment="scenario / scenario+passive / passive"),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["child_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["definition_id"], ["literacy_badge_definitions.id"]),
        )
        op.create_index("ix_literacy_badges_child_id", "literacy_badges", ["child_id"], unique=False)

    # 3. literacy_scenario_templates
    if not _has_table("literacy_scenario_templates"):
        op.create_table(
            "literacy_scenario_templates",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("dimension", sa.String(20), nullable=False),
            sa.Column("age_group", sa.String(10), nullable=False, comment="low (5-7) / mid (8-10) / high (11+)"),
            sa.Column("story_template", sa.Text(), nullable=False),
            sa.Column("choices_json", sa.Text(), nullable=False, comment="JSON array of 2-4 choices with feedback"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_literacy_scenario_templates_dimension", "literacy_scenario_templates", ["dimension"], unique=False)

    # Seed scenario templates (idempotent — keyed by dimension+age_group)
    for idx, (dim, age, story, choices) in enumerate(TEMPLATE_SEEDS):
        existing = bind.execute(
            sa.text("SELECT COUNT(*) FROM literacy_scenario_templates WHERE dimension = :dim AND age_group = :age"),
            {"dim": dim, "age": age},
        ).scalar()
        if existing == 0:
            bind.execute(
                sa.text(
                    "INSERT INTO literacy_scenario_templates (id, dimension, age_group, story_template, choices_json, is_active) "
                    "VALUES (:id, :dim, :age, :story, :choices, :active)"
                ),
                {"id": 2000001 + idx, "dim": dim, "age": age, "story": story, "choices": choices, "active": True},
            )

    # 4. literacy_scenarios
    if not _has_table("literacy_scenarios"):
        op.create_table(
            "literacy_scenarios",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("week_start", sa.Date(), nullable=False),
            sa.Column("template_id", sa.BigInteger(), nullable=False),
            sa.Column("content_json", sa.Text(), nullable=False, comment="Personalized scenario content"),
            sa.Column("choice_index", sa.Integer(), nullable=True),
            sa.Column("feedback_json", sa.Text(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("child_id", "week_start", name="uq_literacy_scenario_child_week"),
            sa.ForeignKeyConstraint(["child_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["template_id"], ["literacy_scenario_templates.id"]),
        )
        op.create_index("ix_literacy_scenarios_child_id", "literacy_scenarios", ["child_id"], unique=False)
        op.create_index("ix_literacy_scenarios_week_start", "literacy_scenarios", ["week_start"], unique=False)

    # 5. literacy_weekly_reports
    if not _has_table("literacy_weekly_reports"):
        op.create_table(
            "literacy_weekly_reports",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("week_start", sa.Date(), nullable=False),
            sa.Column("report_json", sa.Text(), nullable=False, comment="Structured report data"),
            sa.Column("narrative", sa.Text(), nullable=False, comment="AI-generated narrative text"),
            sa.Column("generated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("child_id", "week_start", name="uq_literacy_report_child_week"),
            sa.ForeignKeyConstraint(["child_id"], ["users.id"]),
        )
        op.create_index("ix_literacy_weekly_reports_child_id", "literacy_weekly_reports", ["child_id"], unique=False)
        op.create_index("ix_literacy_weekly_reports_week_start", "literacy_weekly_reports", ["week_start"], unique=False)

    # 6. Alter child_economy_configs — add literacy badge coin columns
    if not _has_column("child_economy_configs", "literacy_badge_coin_enabled"):
        with op.batch_alter_table("child_economy_configs") as batch_op:
            batch_op.add_column(
                sa.Column("literacy_badge_coin_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false"))
            )
    if not _has_column("child_economy_configs", "literacy_badge_coin_amount"):
        with op.batch_alter_table("child_economy_configs") as batch_op:
            batch_op.add_column(
                sa.Column("literacy_badge_coin_amount", sa.Integer(), nullable=False, server_default="50")
            )


def downgrade() -> None:
    bind = op.get_bind()

    def _has_column(table: str, col: str) -> bool:
        if not bind.dialect.has_table(bind, table):
            return False
        cols = {c["name"] for c in bind.dialect.get_columns(bind, table)}
        return col in cols

    if _has_column("child_economy_configs", "literacy_badge_coin_amount"):
        with op.batch_alter_table("child_economy_configs") as batch_op:
            batch_op.drop_column("literacy_badge_coin_amount")
    if _has_column("child_economy_configs", "literacy_badge_coin_enabled"):
        with op.batch_alter_table("child_economy_configs") as batch_op:
            batch_op.drop_column("literacy_badge_coin_enabled")

    op.drop_table("literacy_weekly_reports")
    op.drop_table("literacy_scenarios")
    op.drop_table("literacy_scenario_templates")
    op.drop_table("literacy_badges")
    op.drop_table("literacy_badge_definitions")
