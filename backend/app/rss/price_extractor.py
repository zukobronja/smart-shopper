"""
Enhanced RSS price extraction with multiple strategies.
Based on frontend price detection logic with additional extraction methods.
"""
import re
import logging
import asyncio
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse
import aiohttp
from bs4 import BeautifulSoup

from app.config import settings
from app.extractors.tavily_client import OptimizedTavilyClient

logger = logging.getLogger(__name__)


class EnhancedRSSPriceExtractor:
    """Multi-strategy price extraction for RSS feed items"""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._tavily_client = None
        
        # Currency patterns from frontend with comprehensive global coverage
        self.currency_patterns = [
            # Symbol-based patterns (specific currency prefixes must come before generic $)
            (r'C\$(\d+(?:,\d{3})*(?:\.\d{2})?)', 'CAD', 'C$'),  # Canadian dollar must come before USD
            (r'A\$(\d+(?:,\d{3})*(?:\.\d{2})?)', 'AUD', 'A$'),  # Australian dollar  
            (r'HK\$(\d+(?:,\d{3})*(?:\.\d{2})?)', 'HKD', 'HK$'),  # Hong Kong dollar
            (r'S\$(\d+(?:,\d{3})*(?:\.\d{2})?)', 'SGD', 'S$'),  # Singapore dollar
            (r'NZ\$(\d+(?:,\d{3})*(?:\.\d{2})?)', 'NZD', 'NZ$'),  # New Zealand dollar
            (r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', 'USD', '$'),  # USD must come after specific prefixes
            (r'€(\d+(?:,\d{3})*(?:\.\d{2})?)', 'EUR', '€'),
            (r'£(\d+(?:,\d{3})*(?:\.\d{2})?)', 'GBP', '£'),
            (r'¥(\d+(?:,\d{3})*(?:\.\d{2})?)', 'JPY', '¥'),
            (r'₹(\d+(?:,\d{3})*(?:\.\d{2})?)', 'INR', '₹'),
            (r'₪(\d+(?:,\d{3})*(?:\.\d{2})?)', 'ILS', '₪'),
            (r'₩(\d+(?:,\d{3})*(?:\.\d{2})?)', 'KRW', '₩'),
            
            # Text-based patterns
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:usd|dollars?))', 'USD', '$'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:eur|euros?))', 'EUR', '€'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:gbp|pounds?))', 'GBP', '£'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:aed|dirhams?))', 'AED', 'د.إ'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:jpy|yen))', 'JPY', '¥'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:inr|rupees?))', 'INR', '₹'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:cad|canadian))', 'CAD', 'C$'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:aud|australian))', 'AUD', 'A$'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:chf|swiss))', 'CHF', '₣'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:cny|yuan|rmb))', 'CNY', '¥'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:krw|won))', 'KRW', '₩'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:sgd|singapore))', 'SGD', 'S$'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:hkd|hong\s*kong))', 'HKD', 'HK$'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:nzd|new\s*zealand))', 'NZD', 'NZ$'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:sek|krona))', 'SEK', 'kr'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:nok|norwegian))', 'NOK', 'kr'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dkk|danish))', 'DKK', 'kr'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:ils|shekel|shekels))', 'ILS', '₪'),
        ]
        
        # Deal-specific patterns (order matters - current prices should be found first)
        self.deal_patterns = [
            (r'(?:now|sale|deal|special)\s+[\$€£¥₹₪₩C]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', 'current'),
            (r'(?:was|originally|regular|msrp)\s+[\$€£¥₹₪₩C]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', 'original'),
            (r'save\s+[\$€£¥₹₪₩C]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', 'savings'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*%\s*off', 'percent_off'),
            (r'[\$€£¥₹₪₩C]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:off|discount)', 'discount'),
        ]
        
        # Common e-commerce price CSS selectors
        self.price_selectors = [
            '[data-testid*="price"]', '.price', '.current-price', 
            '.sale-price', '.offer-price', '[class*="price"]',
            'span[class*="Price"]', '.product-price', '.deal-price',
            '.price-current', '.price-now', '.price-sale',
            '[data-price]', '[data-original-price]', '[data-sale-price]',
            '.price-box .price', '.pricing .price', '.cost',
            # Deal-specific selectors
            '.deal-price', '.coupon-price', '.promo-price',
            '.discount-price', '.special-price', '.clearance-price'
        ]

    async def extract_price(self, entry: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
        """
        Extract price using multiple strategies in priority order:
        1. RSS metadata fields
        2. Text analysis of summary/description  
        3. Web scraping (if enabled)
        4. Tavily extraction (if enabled)
        """
        
        # Strategy 1: RSS Metadata Mining
        price, currency = self._extract_from_metadata(entry)
        if price is not None:
            logger.debug(f"Price extracted from metadata: {price} {currency}")
            return price, currency
        
        # Strategy 2: Text Analysis
        text_sources = [
            entry.get("summary", ""),
            entry.get("description", ""),
            entry.get("title", "")
        ]
        
        for text in text_sources:
            if text:
                price, currency = self._extract_from_text(text)
                if price is not None:
                    logger.debug(f"Price extracted from text: {price} {currency}")
                    return price, currency
        
        # Strategy 3: Web Scraping (if enabled and has link)
        link = entry.get("link")
        if (link and settings.RSS_ENABLE_WEB_SCRAPING and 
            self._session is not None and self._should_scrape_link(link)):
            try:
                price, currency = await self._extract_from_web(link)
                if price is not None:
                    logger.debug(f"Price extracted from web scraping: {price} {currency}")
                    return price, currency
            except Exception as e:
                logger.debug(f"Web scraping failed for {link}: {e}")
        
        # Strategy 4: Tavily Extraction (if enabled)
        if link and settings.TAVILY_RSS_FEED_INGESTION:
            try:
                price, currency = await self._extract_with_tavily(link)
                if price is not None:
                    logger.debug(f"Price extracted with Tavily: {price} {currency}")
                    return price, currency
            except Exception as e:
                logger.debug(f"Tavily extraction failed for {link}: {e}")
        
        return None, None

    def _extract_from_metadata(self, entry: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
        """Extract price from RSS custom fields and namespaces"""
        
        # Common RSS commerce extensions and custom fields
        price_fields = [
            'price', 'g:price', 'price_amount', 'sale_price',
            'regular_price', 'offer_price', 'deal_price', 'current_price',
            'product_price', 'list_price', 'retail_price', 'msrp'
        ]
        
        currency_fields = [
            'currency', 'price_currency', 'g:currency', 
            'sale_currency', 'offer_currency', 'product_currency'
        ]
        
        # Check direct fields
        for field in price_fields:
            if field in entry and entry[field]:
                try:
                    price_str = str(entry[field]).strip()
                    # Clean price string
                    price_str = re.sub(r'[^\d.,]', '', price_str)
                    price_str = price_str.replace(',', '')
                    
                    price = float(price_str)
                    if price > 0:
                        # Find corresponding currency
                        currency = None
                        for curr_field in currency_fields:
                            if curr_field in entry and entry[curr_field]:
                                currency = str(entry[curr_field]).upper()
                                break
                        
                        return price, currency or 'USD'
                        
                except (ValueError, TypeError):
                    continue
        
        # Check nested objects (some RSS feeds have structured data)
        for value in entry.values():
            if isinstance(value, dict):
                nested_price, nested_currency = self._extract_from_metadata(value)
                if nested_price is not None:
                    return nested_price, nested_currency
        
        return None, None

    def _extract_from_text(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract price from text using comprehensive regex patterns"""
        
        if not text or len(text.strip()) < 3:
            return None, None
            
        text = text.lower()
        
        # First try deal-specific patterns to handle sales/discounts correctly
        current_price = None
        original_price = None
        deal_currency = None
        
        for pattern, pattern_type in self.deal_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1)
                    amount_str = re.sub(r'[^\d.]', '', amount_str)
                    price = float(amount_str)
                    
                    if 0.50 <= price <= 999999:  # Reasonable price range
                        if pattern_type == 'current' and current_price is None:
                            current_price = price
                            # Try to detect currency from the matched text
                            full_match = match.group(0)
                            if '$' in full_match:
                                deal_currency = 'USD'
                            elif '€' in full_match:
                                deal_currency = 'EUR'
                            elif '£' in full_match:
                                deal_currency = 'GBP'
                        elif pattern_type == 'original' and original_price is None:
                            original_price = price
                            if deal_currency is None:
                                full_match = match.group(0)
                                if '$' in full_match:
                                    deal_currency = 'USD'
                                elif '€' in full_match:
                                    deal_currency = 'EUR'
                                elif '£' in full_match:
                                    deal_currency = 'GBP'
                        
                except (ValueError, IndexError):
                    continue
        
        # Prefer current price over original price for deals
        if current_price is not None:
            return current_price, deal_currency or 'USD'
        elif original_price is not None:
            return original_price, deal_currency or 'USD'
        
        # Fallback to general currency-specific patterns
        for pattern, currency, _symbol in self.currency_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Extract numeric part, removing commas and non-digits except decimal
                    amount_str = match.group(1)
                    amount_str = re.sub(r'[^\d.]', '', amount_str)
                    
                    price = float(amount_str)
                    if 0.50 <= price <= 999999:  # Reasonable price range (minimum 50 cents)
                        return price, currency
                except (ValueError, IndexError):
                    continue
        
        return None, None

    def _should_scrape_link(self, link: str) -> bool:
        """Determine if we should scrape this link based on domain and safety"""
        
        try:
            domain = urlparse(link).netloc.lower()
            
            # Skip known problematic domains that block bots aggressively
            blocked_domains = {
                'amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr',
                'amazon.ca', 'amazon.it', 'amazon.es', 'amazon.in',
                'walmart.com', 'target.com', 'costco.com',
                'alibaba.com', 'ebay.com'  # eBay varies by listing
            }
            
            # Check if domain is in blocked list
            for blocked in blocked_domains:
                if blocked in domain:
                    logger.debug(f"Skipping scraping for blocked domain: {domain}")
                    return False
            
            # Allow scraping for other domains
            return True
            
        except Exception:
            return False

    async def _extract_from_web(self, link: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract price from web page using lightweight scraping"""
        
        if not self._session:
            return None, None
            
        try:
            # Set user agent to avoid some basic bot detection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with self._session.get(
                link, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=settings.RSS_SCRAPING_TIMEOUT)
            ) as resp:
                
                # Check for bot detection status codes
                if resp.status in [403, 429, 503]:
                    logger.debug(f"Bot detection suspected for {link}, status: {resp.status}")
                    return None, None
                    
                if resp.status != 200:
                    return None, None
                
                # Only process HTML content
                content_type = resp.headers.get('Content-Type', '').lower()
                if 'text/html' not in content_type:
                    return None, None
                
                html = await resp.text()
                return self._parse_price_from_html(html)
                
        except asyncio.TimeoutError:
            logger.debug(f"Timeout scraping {link}")
            return None, None
        except Exception as e:
            logger.debug(f"Error scraping {link}: {e}")
            return None, None

    def _parse_price_from_html(self, html: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract price from HTML using CSS selectors and text patterns"""
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try CSS selectors first
            for selector in self.price_selectors:
                elements = soup.select(selector)
                for element in elements:
                    price_text = element.get_text(strip=True)
                    if price_text:
                        price, currency = self._extract_from_text(price_text)
                        if price is not None:
                            return price, currency
            
            # Fallback to full text analysis
            page_text = soup.get_text()
            return self._extract_from_text(page_text)
            
        except Exception as e:
            logger.debug(f"HTML parsing error: {e}")
            return None, None

    async def _extract_with_tavily(self, link: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract price using Tavily structured extraction"""
        
        if not self._tavily_client:
            self._tavily_client = OptimizedTavilyClient()
        
        try:
            result = await self._tavily_client.extract_structured(
                urls=[link],
                schema={
                    "type": "object",
                    "properties": {
                        "price": {"type": "number", "description": "Current price of the product"},
                        "currency": {"type": "string", "description": "Currency code (USD, EUR, etc.)"},
                        "original_price": {"type": "number", "description": "Original price if on sale"},
                        "availability": {"type": "string", "description": "Product availability status"}
                    }
                },
                max_extraction_pages=1
            )
            
            if result and result.get('results'):
                data = result['results'][0]
                price = data.get('price')
                currency = data.get('currency', 'USD').upper()
                
                if price and isinstance(price, (int, float)) and price > 0:
                    return float(price), currency
                    
                # Try original_price as fallback
                original_price = data.get('original_price')
                if original_price and isinstance(original_price, (int, float)) and original_price > 0:
                    return float(original_price), currency
                    
        except Exception as e:
            logger.debug(f"Tavily extraction error for {link}: {e}")
        
        return None, None


# Convenience function for the RSS worker
async def extract_enhanced_price(
    entry: Dict[str, Any], 
    session: Optional[aiohttp.ClientSession] = None
) -> Tuple[Optional[float], Optional[str]]:
    """Extract price from RSS entry using enhanced strategies"""
    
    extractor = EnhancedRSSPriceExtractor(session)
    return await extractor.extract_price(entry)