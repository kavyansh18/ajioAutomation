import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils.logger import setup_logger

logger = setup_logger()
AJIO_BASE_URL = "https://www.ajio.com"

class AJIOParser:
    """Handles HTML parsing and data extraction logic from resolved AJIO page responses (Requirement 19)."""

    @staticmethod
    def parse_preloaded_state(html_content: str) -> list:
        """
        Primary parser targeting the embedded window.__PRELOADED_STATE__ variable.
        Extracts clean product listing records from server-injected state JSON.
        """
        logger.debug("Attempting to parse product records via preloaded React state...")
        
        # Regex to locate global state declaration
        match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.+?});\s*</script>', html_content)
        if not match:
            match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.+?});', html_content)

        if not match:
            logger.debug("window.__PRELOADED_STATE__ script block was not matched.")
            return []

        try:
            raw_json = match.group(1)
            data = json.loads(raw_json)
            
            grid = data.get("grid", {})
            results = grid.get("results", [])
            entities = grid.get("entities", {})

            if not results or not entities:
                logger.debug("Successfully read preloaded state JSON, but grid data was empty.")
                return []

            products = []
            for pid in results:
                entity = entities.get(pid)
                if not entity:
                    continue

                # Product title from Brand and Product Name
                brand = entity.get("brandTypeName", "").strip()
                name = entity.get("name", "").strip()
                title = f"{brand} {name}".strip() if brand else name

                # Price Extraction
                price_val = None
                price_data = entity.get("price")
                if isinstance(price_data, dict):
                    price_val = price_data.get("value")
                elif isinstance(price_data, (int, float)):
                    price_val = price_data

                # MRP Original Price Extraction
                mrp_val = None
                mrp_data = entity.get("wasPriceData") or entity.get("wasPrice")
                if isinstance(mrp_data, dict):
                    mrp_val = mrp_data.get("value")
                elif isinstance(mrp_data, (int, float)):
                    mrp_val = mrp_data

                if mrp_val is None:
                    mrp_val = price_val

                # Format link URL
                url_path = entity.get("url", "")
                product_url = urljoin(AJIO_BASE_URL, url_path) if url_path else ""

                products.append({
                    "title": title or "Unknown AJIO Product",
                    "price": price_val,
                    "mrp": mrp_val,
                    "link": product_url
                })

            logger.info(f"Successfully extracted {len(products)} products from window.__PRELOADED_STATE__ JSON.")
            return products

        except json.JSONDecodeError as jde:
            logger.debug(f"JSON parsing error inside preloaded state: {jde}")
            return []
        except Exception as e:
            logger.debug(f"Unexpected parsing exception inside preloaded state: {e}")
            return []

    @staticmethod
    def parse_bs4_fallback(html_content: str) -> list:
        """
        Secondary parser utilizing BeautifulSoup to target raw DOM elements.
        In case AJIO has statically rendered structure or modified variables.
        """
        logger.debug("Attempting to parse product records via BeautifulSoup DOM selectors...")
        soup = BeautifulSoup(html_content, "html.parser")
        products = []

        # Find product items using primary selectors (Requirement 19)
        product_elements = soup.select("a.rilrtl-products-list__link")
        
        # Try alternative product-container class if standard elements are missing
        if not product_elements:
            product_elements = soup.select(".product-container")

        for p_el in product_elements:
            try:
                # Select brand and description/name elements
                brand_el = p_el.select_one("div.brand strong")
                name_el = p_el.select_one("div.name")
                
                brand = brand_el.get_text(strip=True) if brand_el else ""
                name = name_el.get_text(strip=True) if name_el else ""
                title = f"{brand} {name}".strip() if (brand or name) else "Unknown Product"

                # Parse price string
                price_el = p_el.select_one("span.price")
                price_val = None
                if price_el:
                    price_text = price_el.get_text(strip=True)
                    nums = re.findall(r'\d+', price_text.replace(",", ""))
                    if nums:
                        price_val = float(nums[0])

                # Parse original price / MRP string
                mrp_el = p_el.select_one("span.orgPrice") or p_el.select_one("div.offer-price span")
                mrp_val = None
                if mrp_el:
                    mrp_text = mrp_el.get_text(strip=True)
                    nums = re.findall(r'\d+', mrp_text.replace(",", ""))
                    if nums:
                        mrp_val = float(nums[0])

                if mrp_val is None:
                    mrp_val = price_val

                # URL
                href = p_el.get("href", "")
                product_url = urljoin(AJIO_BASE_URL, href) if href else ""

                products.append({
                    "title": title,
                    "price": price_val,
                    "mrp": mrp_val,
                    "link": product_url
                })
            except Exception as e:
                logger.debug(f"Skipped parsing single BeautifulSoup element: {e}")
                continue

        if products:
            logger.info(f"Successfully extracted {len(products)} products using BeautifulSoup DOM selectors.")
        return products
