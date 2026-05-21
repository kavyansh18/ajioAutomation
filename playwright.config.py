# Playwright Scraper Configuration
# Contains standard config settings for Chromium headless execution.

PLAYWRIGHT_CONFIG = {
    "browser_type": "chromium",
    "headless": True, # Can be toggled dynamically via DEBUG env variable
    "viewport": {
        "width": 1280,
        "height": 800
    },
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "locale": "en-US",
    "timezone_id": "Asia/Kolkata",
    "default_timeout": 30000, # 30 seconds
    "ignore_https_errors": True
}
