import logging
import random

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.services.exchange_rate import ExchangeRateService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def fetch_rates_job() -> None:
    """APScheduler job: fetch and store latest exchange rates."""
    db = SessionLocal()
    try:
        ExchangeRateService.fetch_and_store_rates(db)
    except Exception as e:
        logger.exception(f"定时汇率更新失败: {e}")
    finally:
        db.close()


def setup_exchange_rate_schedule() -> None:
    """Schedule rate updates every 2 hours from 08:00 to 22:00 with random 0-15 min offset."""
    for hour in [8, 10, 12, 14, 16, 18, 20, 22]:
        offset = random.randint(0, 15)
        scheduler.add_job(
            fetch_rates_job,
            trigger="cron",
            hour=hour,
            minute=offset,
            id=f"exchange_rate_{hour}",
            replace_existing=True,
        )
    logger.info("汇率定时任务已配置（每2小时，08:00-22:00）")