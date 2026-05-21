import os
import requests
from utils.logger import setup_logger

logger = setup_logger()

class TelegramNotifier:
    """
    Handles secure communication with the Telegram Bot API to dispatch price alerts.
    
    Why Telegram Bot Secrets are set via Environment Variables (Requirement 19):
    - Hardcoding tokens directly in standard git repositories is a major security risk that can allow unauthorized access to bots.
    - Setting secrets via environment variables separates credentials from the application code. This complies with 12-factor app security principles.
    - In GitHub Actions, secrets are encrypted in Repository Settings and safely injected at runtime, preventing public leaks.
    """

    def __init__(self):
        # Fetch tokens securely from the environment
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def validate_credentials(self) -> bool:
        """Verifies that both the token and chat ID are configured in the environment."""
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram credentials missing! Ensure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set.")
            return False
        return True

    def send_message(self, text: str) -> bool:
        """
        Sends a generic text message to the configured Telegram chat.
        """
        if not self.validate_credentials():
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            res_json = response.json()
            if response.status_code == 200 and res_json.get("ok"):
                return True
            else:
                logger.error(
                    f"Telegram API error (Status Code {response.status_code}): {response.text}"
                )
                return False
        except Exception as e:
            logger.error(f"Failed to communicate with Telegram Bot API: {e}", exc_info=True)
            return False

    def send_alert(self, product: dict) -> bool:
        """
        Sends a price drop alert message to the configured Telegram chat.
        """
        # Exact format specified in requirement 5
        message_text = (
            "🚨 AJIO ALERT 🚨\n\n"
            f"Product: {product.get('title', 'Unknown')}\n"
            f"Price: ₹{product.get('price', 'N/A')}\n"
            f"MRP: ₹{product.get('mrp', 'N/A')}\n"
            f"Link: {product.get('link', '')}"
        )

        logger.info(f"Dispatching Telegram price alert for: {product.get('title')}")
        delivered = self.send_message(message_text)
        if delivered:
            logger.info("Telegram alert delivered successfully!")
        return delivered
