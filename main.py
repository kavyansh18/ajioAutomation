#!/usr/bin/env python3
"""
AJIO Price Monitor - Main Orchestrator

This script coordinates the Playwright Chromium scraping cycle,
data extraction, price condition validation, and Telegram alerts dispatch.

Why browser automation (Playwright) is used instead of requests (Requirement 15):
- AJIO beauty listings are protected by Akamai Web Application Firewall (WAF).
- Raw HTTP client requests lack realistic TLS handshakes, screen rendering profiles,
  and JS engine environments, and are blocked immediately with '403 Access Denied' errors.
- By utilizing a real Chromium browser in stealth mode via Playwright, we can navigate
  successfully, bypass blocks, and load the dynamic listings cleanly.
"""

import os
import sys

# Add utility modules imports (Requirement 11)
from utils.logger import setup_logger
from utils.scraper import AJIOScraper
from utils.parser import AJIOParser
from utils.telegram import TelegramNotifier

# Load local environment variables from dotenv if locally executed (Requirement 6)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Initialize logger
logger = setup_logger()


class AJIOMonitor:
    """Main program orchestrator managing scraper execution, price validation, and alert messaging."""

    def __init__(self):
        self.scraper = AJIOScraper()
        self.notifier = TelegramNotifier()
        self.debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    def validate_and_alert(self, products: list) -> bool:
        """
        Scans the top 4 products and dispatches alerts for conditions under ₹10.
        """
        # Limit analysis to first 4 products (Requirement 3)
        target_count = min(4, len(products))
        monitored_list = products[:target_count]

        # 7. Local Testing Support: Print all extracted products and prices if debug mode is active
        if self.debug_mode:
            logger.info("--- LOCAL TESTING: ALL EXTRACTED PRODUCTS ---")
            for idx, p in enumerate(products):
                logger.info(f"Product {idx+1}: '{p['title']}' | Price: {p['price']} | MRP: {p['mrp']}")
            logger.info("---------------------------------------------")

        logger.info(f"Scanning the top {target_count} lowest-priced products on AJIO:")
        
        alerts_triggered = False
        triggered_products = []

        for idx, p in enumerate(monitored_list):
            raw_price = p.get("price")
            raw_mrp = p.get("mrp")

            # 1. & 5. Safe Numeric Price Parsing
            try:
                if raw_price is None or raw_mrp is None:
                    logger.warning(f"Skipping product '{p['title']}' due to missing price/mrp fields.")
                    continue
                
                # Convert value to clean string and parse safely
                price_val = float(str(raw_price).replace("₹", "").replace(",", "").strip())
                mrp_val = float(str(raw_mrp).replace("₹", "").replace(",", "").strip())
            except (ValueError, TypeError) as parse_err:
                logger.warning(
                    f"Skipping product '{p['title']}' safely due to parsing failure. "
                    f"Raw Price: '{raw_price}', Raw MRP: '{raw_mrp}'. Error: {parse_err}"
                )
                continue

            # Update product dict with clean float conversions
            p["price"] = price_val
            p["mrp"] = mrp_val

            # 2. New Alert Condition (< ₹10)
            condition_matched = (price_val < 10.0) or (mrp_val < 10.0)

            # 4. Add Debug Logging
            logger.info(f"Product {idx+1}: '{p['title']}'")
            logger.info(f"  Parsed price: {price_val}")
            logger.info(f"  Parsed MRP: {mrp_val}")
            logger.info(f"  Condition matched: {condition_matched}")

            if condition_matched:
                triggered_products.append(p)
                logger.warning(
                    f"PRICE ALERT MATCHED: Product {idx+1} '{p['title']}' is under ₹10. Price: ₹{price_val}, MRP: ₹{mrp_val}."
                )
                delivered = self.notifier.send_alert(p)
                if delivered:
                    alerts_triggered = True

        if self.debug_mode:
            logger.info("=== LOCAL TESTING TRIGGER SUMMARY ===")
            logger.info(f"Total monitored: {len(monitored_list)}")
            logger.info(f"Triggered alerts: {len(triggered_products)} product(s)")
            for tp in triggered_products:
                logger.info(f"  -> Triggered: '{tp['title']}' | Price: ₹{tp['price']} | MRP: ₹{tp['mrp']}")
            logger.info("=====================================")

        # Debug Mode artificial alert dispatch
        if self.debug_mode and not alerts_triggered:
            logger.info("DEBUG MODE: Initiating a test Telegram alert to verify configuration...")
            debug_product = {
                "title": "TEST AJIO PRODUCT (Debug Mode Activity)",
                "price": 1.50,
                "mrp": 1500.0,
                "link": "https://www.ajio.com/s/beauty-5269-65820?query=%3Aprce-asc"
            }
            self.notifier.send_alert(debug_product)
            alerts_triggered = True

        return alerts_triggered

    def run(self):
        """Executes the complete monitor sequence with solid exception boundaries (Requirement 7)."""
        logger.info("=== Starting Playwright AJIO Price Monitor Cycle ===")
        
        # Verify Telegram configuration before wasting scraper resources
        if not self.notifier.validate_credentials():
            logger.critical("Scraper halted: Missing necessary Telegram configuration variables.")
            sys.exit(1)

        try:
            # 1. Fetch resolved HTML content via Playwright Chromium
            html = self.scraper.fetch_page_content_with_retry()
            if not html:
                logger.error("Scraper cycle terminated: Unable to resolve listing page source.")
                sys.exit(1)

            # 2. Parse products list (React state primary, BeautifulSoup fallback)
            products = AJIOParser.parse_preloaded_state(html)
            if not products:
                logger.info("React preloaded state parse returned 0 products. Running BeautifulSoup fallback...")
                products = AJIOParser.parse_bs4_fallback(html)

            if not products:
                logger.error("Failed to extract any product listing records from page source.")
                sys.exit(1)

            logger.info(f"Successfully extracted {len(products)} total listing products from search category.")

            # 3. Process price drops and dispatch alerts
            alerts_sent = self.validate_and_alert(products)
            if not alerts_sent:
                logger.info("Scan complete: No products met the under-₹10 conditions. Alerts not sent.")

            logger.info("=== AJIO Price Monitor Cycle Completed Cleanly ===")

        except Exception as e:
            # Ensure the script never crashes completely and exits safely (Requirement 7)
            logger.critical(f"Unhandled critical execution error in monitor cycle: {e}", exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    monitor = AJIOMonitor()
    monitor.run()
