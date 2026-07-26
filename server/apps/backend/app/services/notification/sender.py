# backend/app/services/notification/sender.py
import json
import logging
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_template(reminder_type: str, channel_type: str, variables: dict) -> str:
    """加载模板并用 variables 渲染，返回渲染后的文本。

    channel_type 可选值：
    - "telegram" → 返回 telegram.text
    - "email_subject" → 返回 email.subject
    - "email_body" → 返回 email.body
    """
    template_path = _TEMPLATE_DIR / f"{reminder_type}.json"
    with open(template_path, encoding="utf-8") as f:
        tmpl = json.load(f)
    if channel_type == "telegram":
        return str(tmpl["telegram"]["text"].format_map(variables))
    elif channel_type == "email_subject":
        return str(tmpl["email"]["subject"].format_map(variables))
    elif channel_type == "email_body":
        return str(tmpl["email"]["body"].format_map(variables))
    raise ValueError(f"Unknown channel_type: {channel_type}")


class NotificationSender:
    """封装 Telegram 和 SMTP 发送逻辑。"""

    @staticmethod
    async def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                )
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.warning("Telegram 发送失败: %s", e)
            return False

    @staticmethod
    def send_email(
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        smtp_from: str,
        to: str,
        subject: str,
        body: str,
    ) -> bool:
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = to
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [to], msg.as_string())
            return True
        except Exception as e:
            logger.warning("邮件发送失败: %s", e)
            return False
