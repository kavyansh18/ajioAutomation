import os
import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
import importlib.util
from playwright_stealth import Stealth
from utils.logger import setup_logger

# Load local playwright.config.py dynamically to prevent namespace shadowing (Requirement 11)
spec = importlib.util.spec_from_file_location("local_playwright_config", "playwright.config.py")
playwright_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(playwright_config)
PLAYWRIGHT_CONFIG = playwright_config.PLAYWRIGHT_CONFIG


logger = setup_logger()

# Sorted categories low-to-high AJIO URL (Requirement 2)
AJIO_URL = "https://www.ajio.com/s/beauty-5269-65820?query=%3Aprce-asc&curated=true&curatedid=beauty-5269-65820&customerType=New&gridColumns=3&sort=relevance"

class AJIOScraper:
    """Manages Playwright browser launch, context initialization, stealth injection, and page navigations."""

    def __init__(self):
        self.debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        # Run headed browser locally if DEBUG=true, headless otherwise (Requirement 11)
        self.headless = not self.debug_mode
        self.screenshots_dir = "screenshots"
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Load and validate ScraperAPI Residential Proxy key (Requirement 2)
        self.scraperapi_key = os.getenv("SCRAPERAPI_KEY")
        if not self.scraperapi_key:
            logger.warning("SCRAPERAPI_KEY environment variable is not defined. Proxy routing will fail without a key.")

    def _apply_stealth_settings(self, context: BrowserContext, page: Page):
        """Applies stealth overrides to mask webdriver signatures and emulate human attributes."""
        logger.debug("Injecting playwright-stealth configurations into page context...")
        Stealth().apply_stealth_sync(page)

        
        # Additional custom evasions for navigator properties
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = {
                runtime: {}
            };
        """)

    def capture_diagnostics(self, page: Page, name_prefix: str = "failure"):
        """Captures page screenshots and downloads HTML dump files for diagnostic debugging."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save screenshot
        screenshot_path = os.path.join(self.screenshots_dir, f"{name_prefix}_{timestamp}.png")
        try:
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Diagnostic screenshot successfully saved to: {screenshot_path}")
        except Exception as e:
            logger.error(f"Failed to capture diagnostic screenshot: {e}")

        # Save HTML source
        html_path = "page_source.html"
        try:
            html_content = page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"Diagnostic HTML page layout successfully saved to: {html_path}")
        except Exception as e:
            logger.error(f"Failed to save page layout HTML: {e}")

    def fetch_page_content_with_retry(self, max_retries: int = 3) -> str:
        """
        Launches Playwright Chromium browser and navigates to the AJIO target URL via ScraperAPI Render endpoint.
        Includes built-in retries, stealth masking, block detection, and failure screenshot capturing.
        """
        # Validate SCRAPERAPI_KEY exists (Requirement 6)
        if not self.scraperapi_key:
            logger.critical("SCRAPERAPI_KEY is missing from the environment. Scraper terminated safely.")
            return ""
            
        logger.info("SCRAPERAPI_KEY loaded successfully.")
        logger.info("Using ScraperAPI rendered fetch endpoint...")
        import urllib.parse
        encoded_url = urllib.parse.quote_plus(AJIO_URL)
        SCRAPERAPI_URL = (
            f"http://api.scraperapi.com/"
            f"?api_key={self.scraperapi_key}"
            f"&url={encoded_url}"
        )
        logger.info("ScraperAPI URL generated successfully.")
        
        logger.info("Launching Chromium without proxy mode")
        logger.info(f"Launching Playwright Chromium browser (Headless={self.headless}). Max retries: {max_retries}")
        
        # Start Playwright
        with sync_playwright() as p:
            for attempt in range(1, max_retries + 1):
                logger.info(f"Scraper Run Attempt {attempt}/{max_retries}...")
                
                try:
                    # Launch standard browser context without proxy (Requirement 1 & 2)
                    browser: Browser = p.chromium.launch(
                        headless=self.headless,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-web-security",
                            "--disable-infobars",
                            "--window-size=1280,800"
                        ]
                    )
                    logger.debug("Chromium browser process successfully initialized.")
 
                    # Create context with realistic locale, viewport, and agent (Requirement 1 & 8)
                    context: BrowserContext = browser.new_context(
                        viewport=PLAYWRIGHT_CONFIG["viewport"],
                        user_agent=PLAYWRIGHT_CONFIG["user_agent"],
                        locale=PLAYWRIGHT_CONFIG["locale"],
                        timezone_id=PLAYWRIGHT_CONFIG["timezone_id"],
                        ignore_https_errors=PLAYWRIGHT_CONFIG["ignore_https_errors"]
                    )
                    
                    # Set short default timeout limit
                    context.set_default_timeout(PLAYWRIGHT_CONFIG["default_timeout"])
                    page: Page = context.new_page()
 
                    # Apply playwright-stealth evasions (Requirement 1 & 8)
                    self._apply_stealth_settings(context, page)
 
                    # Add light randomized delay before navigation to improve stability (Fix 3)
                    time.sleep(random.uniform(2, 6))

                    # Navigation and loading
                    logger.info("Navigating to ScraperAPI target render URL...")
                    
                    # Open direct URL and wait until DOM contents are fully resolved (Requirement 4)
                    response = page.goto(
                        SCRAPERAPI_URL,
                        wait_until="domcontentloaded",
                        timeout=120000
                    )
                    
                    if response is None:
                        logger.warning("Empty response received from AJIO page navigate call.")
                        self.capture_diagnostics(page, "empty_response")
                        browser.close()
                        continue
                        
                    logger.info(f"Page response loaded. HTTP Status: {response.status}")
                    
                    # 1. Detect WAF / Access Denied page responses or proxy server failures (Requirement 8)
                    html_content = page.content()
                    if response.status != 200 or "access denied" in html_content.lower() or "captcha" in html_content.lower():
                        logger.warning(f"Page loading check failed. HTTP Status: {response.status}")
                        self.capture_diagnostics(page, "loading_failure")
                        browser.close()
                        
                        if attempt < max_retries:
                            sleep_time = random.uniform(4.0, 8.0) * attempt
                            logger.info(f"Waiting for randomized backoff of {sleep_time:.2f} seconds before retrying...")
                            time.sleep(sleep_time)
                            continue
                        else:
                            logger.error("Scraper retries exhausted due to persistent HTTP failures or blocks.")
                            return ""

                    # 2. Wait for target selectors or fallback loading tags (Requirement 19 & 20)
                    logger.debug("Waiting for AJIO listing container elements to render...")
                    try:
                        # Wait for either standard products selector or fallback layout container
                        page.wait_for_selector("a.rilrtl-products-list__link", timeout=15000)
                    except Exception as select_err:
                        logger.warning(f"wait_for_selector timed out or failed: {select_err}")
                        # Take quick screenshot to verify layout structure
                        self.capture_diagnostics(page, "selector_timeout")

                    # Emulate slight randomized human delay before reading contents (Requirement 1 & 20)
                    human_wait = random.uniform(1.5, 3.5)
                    logger.debug(f"Applying pre-read human delay: {human_wait:.2f} seconds...")
                    time.sleep(human_wait)

                    # Return resolved HTML layout source
                    resolved_html = page.content()
                    browser.close()
                    return resolved_html

                except Exception as attempt_err:
                    logger.error(f"Error encountered during scraper attempt {attempt}: {attempt_err}")
                    if attempt < max_retries:
                        sleep_time = random.uniform(3, 6)
                        logger.info(f"Waiting {sleep_time:.2f} seconds before retrying...")
                        time.sleep(sleep_time)
                    else:
                        logger.critical("Scraper run failed completely on final retry attempt.")
            
            return ""
