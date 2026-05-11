from app.models.activity import Activity  # noqa: F401
from app.models.ai_allocation_target import AIAllocationTarget  # noqa: F401
from app.models.ai_asset_alert import AIAssetAlert  # noqa: F401
from app.models.ai_chat_message import AIChatMessage  # noqa: F401
from app.models.ai_chat_session import AIChatSession  # noqa: F401
from app.models.ai_disposal_suggestion import AIDisposalSuggestion  # noqa: F401
from app.models.ai_provider_config import (  # noqa: F401
    AIProviderConfig,
    AIProviderTestResult,
)
from app.models.ai_report import AIReport  # noqa: F401
from app.models.ai_spending_leak import AISpendingLeak  # noqa: F401
from app.models.ai_task import AITask  # noqa: F401
from app.models.ai_ws_ticket import AIWsTicket  # noqa: F401
from app.models.asset import Asset  # noqa: F401
from app.models.asset_lifecycle_event import AssetLifecycleEvent  # noqa: F401
from app.models.blind_box_config import BlindBoxConfig  # noqa: F401
from app.models.blind_box_draw import BlindBoxDraw  # noqa: F401
from app.models.blind_box_gift import BlindBoxGift  # noqa: F401
from app.models.bonus_draw import BonusDraw  # noqa: F401
from app.models.cached_file import CachedFile  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.category_financial_default import CategoryFinancialDefault  # noqa: F401
from app.models.child_economy_config import ChildEconomyConfig  # noqa: F401
from app.models.child_milestone import ChildMilestone  # noqa: F401
from app.models.child_wish import ChildWish  # noqa: F401
from app.models.child_wish_cost_history import ChildWishCostHistory  # noqa: F401
from app.models.chore import ChoreInstance, ChoreTemplate  # noqa: F401
from app.models.coin_transaction import CoinTransaction  # noqa: F401
from app.models.currency import Currency  # noqa: F401
from app.models.device_session import DeviceSession  # noqa: F401
from app.models.exchange_rate import ExchangeRate  # noqa: F401
from app.models.family import Family  # noqa: F401
from app.models.family_invitation_code import FamilyInvitationCode  # noqa: F401
from app.models.family_mcp_server import FamilyMCPServer  # noqa: F401
from app.models.family_skill_config import FamilySkillConfig  # noqa: F401
from app.models.file_remote_location import FileRemoteLocation  # noqa: F401
from app.models.liability import Liability  # noqa: F401
from app.models.notification_channel import NotificationChannel  # noqa: F401
from app.models.notification_channel_config import (
    NotificationChannelConfig,  # noqa: F401
)
from app.models.notification_config import NotificationConfig  # noqa: F401
from app.models.notification_subscription import NotificationSubscription  # noqa: F401
from app.models.payment_record import PaymentRecord  # noqa: F401
from app.models.reminder import Reminder  # noqa: F401
from app.models.reminder_notification import ReminderNotification  # noqa: F401
from app.models.revoked_token import RevokedToken  # noqa: F401
from app.models.security_audit_log import SecurityAuditLog  # noqa: F401
from app.models.snapshot import AssetSnapshot  # noqa: F401
from app.models.storage_backend import StorageBackend  # noqa: F401
from app.models.sync_event import SyncEvent  # noqa: F401
from app.models.tag import Tag  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.valuation import AssetValuation  # noqa: F401
from app.models.wish import Wish  # noqa: F401
