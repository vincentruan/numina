# backend/app/services/notification/sender.py
import base64
import hashlib
import hmac
import json
import logging
import smtplib
import time
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
    - "feishu" → 返回 feishu.text
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
    elif channel_type == "feishu":
        return str(tmpl["feishu"]["text"].format_map(variables))
    raise ValueError(f"Unknown channel_type: {channel_type}")


class NotificationSender:
    """封装 Telegram、SMTP 和飞书 Webhook 发送逻辑。"""

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

    @staticmethod
    async def send_feishu(webhook_url: str, text: str, secret: str = "") -> bool:
        """通过飞书机器人 Webhook 发送消息。

        secret 可选；若配置则生成签名。
        """
        payload: dict = {
            "msg_type": "text",
            "content": {"text": text},
        }
        if secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(
                string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
            ).digest()
            sign = base64.b64encode(hmac_code).decode("utf-8")
            payload["timestamp"] = timestamp
            payload["sign"] = sign
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                if body.get("code", -1) != 0:
                    logger.warning("飞书发送业务失败: %s", body)
                    return False
                return True
        except Exception as e:
            logger.warning("飞书发送失败: %s", e)
            return False
