# re-exporting models for convenience imports + SQLAlchemy registration
from apps.backend.app.models.activity import Activity
from apps.backend.app.models.ai_agent import AIAgent
from apps.backend.app.models.ai_chat_feedback import AIChatMessageFeedback
from apps.backend.app.models.ai_chat_message import AIChatMessage
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.ai_extraction_circuit import (
    AIExtractionCircuit,
)
from apps.backend.app.models.ai_provider_config import (
    AIProviderConfig,
    AIProviderTestResult,
)
from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.models.ai_task import AITask
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.asset_lifecycle_event import (
    AssetLifecycleEvent,
)
from apps.backend.app.models.blind_box_config import BlindBoxConfig
from apps.backend.app.models.blind_box_draw import BlindBoxDraw
from apps.backend.app.models.blind_box_gift import BlindBoxGift
from apps.backend.app.models.bonus_draw import BonusDraw
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.category import Category
from apps.backend.app.models.category_financial_default import (
    CategoryFinancialDefault,
)
from apps.backend.app.models.challenge_grant import ChallengeGrant
from apps.backend.app.models.child_economy_config import (
    ChildEconomyConfig,
)
from apps.backend.app.models.child_milestone import ChildMilestone
from apps.backend.app.models.child_wish import ChildWish
from apps.backend.app.models.child_wish_cost_history import (
    ChildWishCostHistory,
)
from apps.backend.app.models.chore import ChoreInstance, ChoreTemplate
from apps.backend.app.models.coin_transaction import CoinTransaction
from apps.backend.app.models.currency import Currency
from apps.backend.app.models.device_session import DeviceSession
from apps.backend.app.models.draft_import import DraftImport
from apps.backend.app.models.exchange_rate import ExchangeRate
from apps.backend.app.models.family import Family
from apps.backend.app.models.family_debt_thresholds import FamilyDebtThresholds
from apps.backend.app.models.family_invitation_code import (
    FamilyInvitationCode,
)
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from apps.backend.app.models.file_remote_location import (
    FileRemoteLocation,
)
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.manifesto import (
    FamilyManifesto,
    ManifestoFeedback,
    ManifestoSignature,
    ManifestoVersion,
)
from apps.backend.app.models.notification_channel import (
    NotificationChannel,
)
from apps.backend.app.models.notification_subscription import (
    NotificationSubscription,
)
from apps.backend.app.models.payment_record import PaymentRecord
from apps.backend.app.models.reminder import Reminder
from apps.backend.app.models.reminder_notification import (
    ReminderNotification,
)
from apps.backend.app.models.revoked_token import RevokedToken
from apps.backend.app.models.security_audit_log import SecurityAuditLog
from apps.backend.app.models.skill_registry import SkillRegistry
from apps.backend.app.models.snapshot import AssetSnapshot
from apps.backend.app.models.storage_backend import StorageBackend
from apps.backend.app.models.sync_event import SyncEvent
from apps.backend.app.models.tag import Tag
from apps.backend.app.models.user import User
from apps.backend.app.models.valuation import AssetValuation
from apps.backend.app.models.wish import Wish
from packages.db.models.notification_channel_config import (
    NotificationChannelConfig,
)
from packages.db.models.notification_config import NotificationConfig
