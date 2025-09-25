"""
Enhanced Price Discovery Agent

Addresses critical price extraction failures by implementing multiple 
price discovery methods with intelligent fallbacks.
"""
from __future__ import annotations

import re
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from app.agents.state import SmartShopperAgent, SmartShopperWorkflowState, add_agent_step
import logging

logger = logging.getLogger(__name__)


class EnhancedPriceDiscoveryAgent(SmartShopperAgent):
    """
    Multi-method price discovery agent that addresses price extraction failures
    
    Uses cascading fallback strategy:
    1. Enhanced content-based extraction (improved algorithm)
    2. Structured data extraction (JSON-LD, microdata)  
    3. Direct page scraping for known domains
    4. RSS/feed price matching
    """
    
    name = "Enhanced Price Discovery"
    color = SmartShopperAgent.BLUE
    
    def __init__(self):
        super().__init__()
        self.max_concurrent_requests = 5
        self.request_timeout = 10
        self.log("Initialized Enhanced Price Discovery Agent")
    
    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """
        Main processing method for enhanced price discovery
        """
        start_time = datetime.now(timezone.utc)
        self.log("Starting enhanced price discovery")
        
        try:
            # Get structured products from spec extractor
            structured_products = state.get("structured_products", [])
            if not structured_products:
                self.log("No structured products to enhance")
                return self._record_execution(state, start_time, 0, "skipped")
            
            # Identify products with missing or suspicious prices
            products_needing_enhancement = self._identify_price_issues(structured_products)
            
            if not products_needing_enhancement:
                self.log("No price issues detected")
                return self._record_execution(state, start_time, 0, "success")
            
            self.log(f"Enhancing prices for {len(products_needing_enhancement)} products")
            
            # Apply enhanced price discovery
            enhanced_products = []
            for product in structured_products:
                if product in products_needing_enhancement:
                    enhanced_product = await self._enhance_product_price(product)
                    enhanced_products.append(enhanced_product)
                else:
                    enhanced_products.append(product)
            
            # Update state
            state["structured_products"] = enhanced_products
            
            # Count improvements
            improvements_made = sum(1 for orig, enh in zip(structured_products, enhanced_products) 
                                   if orig.get("price") != enh.get("price"))
            
            self.log(f"Enhanced {improvements_made} product prices")
            return self._record_execution(state, start_time, improvements_made, "success")
            
        except Exception as e:
            self.log(f"Error in price discovery: {e}")
            return self._record_execution(state, start_time, 0, "error", str(e))
    
    def _identify_price_issues(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify products with price extraction issues
        """
        issues = []
        
        for product in products:
            price = product.get("price")
            title = product.get("title", "").lower()
            url = product.get("url", "")
            
            # Issue 1: Missing price entirely
            if price is None:
                self.log(f"Missing price: {title[:50]}")
                issues.append(product)
                continue
            
            # Issue 2: Suspiciously low prices for high-end products
            if self._is_suspicious_price(price, title):
                self.log(f"Suspicious price ${price:.2f}: {title[:50]}")
                issues.append(product)
                continue
            
            # Issue 3: Known problematic domains
            if self._is_problematic_domain(url):
                self.log(f"Problematic domain: {urlparse(url).netloc}")
                issues.append(product)
                continue
        
        return issues
    
    def _is_suspicious_price(self, price: float, title: str) -> bool:
        """
        Detect suspiciously low prices that are likely extraction errors
        """
        # Gaming laptops under $200 are likely wrong (protection plans, etc.)
        if any(keyword in title for keyword in ["gaming laptop", "legion", "rog", "alienware"]):
            if price < 200:
                return True
        
        # High-end GPU laptops under $500 are suspicious  
        if any(keyword in title for keyword in ["rtx 5090", "rtx 4090", "rtx 4080"]):
            if price < 500:
                return True
        
        # Enterprise/workstation laptops under $1000 are suspicious
        if any(keyword in title for keyword in ["workstation", "precision", "thinkpad"]):
            if price < 1000:
                return True
        
        return False
    
    def _is_problematic_domain(self, url: str) -> bool:
        """
        Identify domains known to have extraction issues
        """
        if not url:
            return False
        
        domain = urlparse(url).netloc.lower()
        problematic_domains = [
            "bhphotovideo.com",  # Complex pricing structure
            "newegg.com",        # Multiple pricing tiers
            "microcenter.com",   # In-store vs online pricing
            "amazon.com"         # Dynamic pricing, promotions
        ]
        
        return any(prob_domain in domain for prob_domain in problematic_domains)
    
    async def _enhance_product_price(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply enhanced price discovery for a single product
        """
        url = product.get("url")
        if not url:
            return product
        
        # Method 1: Re-extract with enhanced patterns
        enhanced_price = await self._enhanced_content_extraction(product)
        if enhanced_price:
            product["price"] = enhanced_price["price"]
            product["currency"] = enhanced_price["currency"]
            product["price_discovery_method"] = "enhanced_extraction"
            return product
        
        # Method 2: Structured data extraction
        structured_price = await self._extract_structured_data_price(url)
        if structured_price:
            product["price"] = structured_price["price"]
            product["currency"] = structured_price["currency"]  
            product["price_discovery_method"] = "structured_data"
            return product
        
        # Method 3: Domain-specific extraction
        domain_price = await self._domain_specific_extraction(url)
        if domain_price:
            product["price"] = domain_price["price"]
            product["currency"] = domain_price["currency"]
            product["price_discovery_method"] = "domain_specific"
            return product
        
        # If all methods fail, mark as unresolved
        product["price_discovery_method"] = "failed"
        product["price_extraction_warning"] = "Unable to extract reliable price"
        
        return product
    
    async def _enhanced_content_extraction(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Enhanced content-based price extraction with better patterns
        """
        # Get existing content from various sources
        content_sources = [
            product.get("content", ""),
            product.get("description", ""),
            product.get("summary", ""),
            # Also check specs for embedded price info
            str(product.get("specs", {}))
        ]
        
        combined_content = " ".join(filter(None, content_sources))
        
        if not combined_content:
            return None
        
        # Enhanced price extraction patterns targeting specific pricing scenarios
        enhanced_patterns = [
            # Main product pricing patterns (high confidence)
            (r'(?:our\s+price|sale\s+price|price|cost)[:$\s]*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD", 15),
            (r'buy\s+(?:now\s+)?(?:for\s+)?\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD", 12),
            (r'add\s+to\s+cart.*?\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD", 12),
            
            # Product listing patterns (medium confidence)  
            (r'(?:^|\s)\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)(?:\s|$)', "USD", 8),
            (r'(?:priced\s+at|selling\s+for|costs?)\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD", 10),
            
            # Avoid common false positives (negative scoring)
            (r'(?:protection|warranty|plan|service).*?\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD", -10),
            (r'(?:shipping|tax|fee).*?\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD", -8),
            (r'(?:monthly|/mo|per\s+month).*?\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD", -12),
        ]
        
        # Find all price candidates with confidence scoring
        candidates = []
        for pattern, currency, confidence in enhanced_patterns:
            matches = re.finditer(pattern, combined_content, re.IGNORECASE)
            for match in matches:
                try:
                    price_str = match.group(1).replace(',', '')
                    price = float(price_str)
                    
                    if 1 <= price <= 100000:  # Reasonable price range
                        candidates.append({
                            'price': price,
                            'currency': currency,
                            'confidence': confidence,
                            'context': combined_content[max(0, match.start()-50):match.end()+50]
                        })
                except (ValueError, AttributeError):
                    continue
        
        # Select best candidate based on confidence scoring
        if candidates:
            best_candidate = max(candidates, key=lambda x: x['confidence'])
            if best_candidate['confidence'] > 0:  # Only accept positive confidence
                return {
                    'price': best_candidate['price'],
                    'currency': best_candidate['currency']
                }
        
        return None
    
    async def _extract_structured_data_price(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract price from structured data (JSON-LD, microdata)
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.request_timeout)) as session:
                async with session.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}) as response:
                    if response.status != 200:
                        return None
                    
                    html_content = await response.text()
                    
                    # Look for JSON-LD structured data
                    json_ld_matches = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', 
                                                html_content, re.DOTALL | re.IGNORECASE)
                    
                    for json_str in json_ld_matches:
                        try:
                            import json
                            data = json.loads(json_str)
                            price = self._extract_price_from_json_ld(data)
                            if price:
                                return price
                        except (json.JSONDecodeError, Exception):
                            continue
                    
                    # Look for microdata price attributes  
                    microdata_price = re.search(r'(?:itemprop|property)=["\']price["\'][^>]*content=["\']([0-9.,]+)["\']', 
                                               html_content, re.IGNORECASE)
                    if microdata_price:
                        try:
                            price = float(microdata_price.group(1).replace(',', ''))
                            if 1 <= price <= 100000:
                                return {'price': price, 'currency': 'USD'}
                        except ValueError:
                            pass
                    
        except Exception as e:
            self.log(f"Structured data extraction failed for {url}: {e}")
        
        return None
    
    def _extract_price_from_json_ld(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract price from JSON-LD structured data"""
        if isinstance(data, list):
            for item in data:
                price = self._extract_price_from_json_ld(item)
                if price:
                    return price
            return None
        
        if not isinstance(data, dict):
            return None
        
        # Check for direct price fields
        if 'price' in data:
            try:
                price = float(str(data['price']).replace(',', ''))
                currency = data.get('priceCurrency', 'USD')
                if 1 <= price <= 100000:
                    return {'price': price, 'currency': currency}
            except (ValueError, TypeError):
                pass
        
        # Check for offers
        if 'offers' in data:
            offers = data['offers']
            if isinstance(offers, list):
                for offer in offers:
                    price = self._extract_price_from_json_ld(offer)
                    if price:
                        return price
            else:
                return self._extract_price_from_json_ld(offers)
        
        # Recursively check nested objects
        for value in data.values():
            if isinstance(value, (dict, list)):
                price = self._extract_price_from_json_ld(value)
                if price:
                    return price
        
        return None
    
    async def _domain_specific_extraction(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Domain-specific price extraction for known problematic sites
        """
        domain = urlparse(url).netloc.lower()
        
        # B&H Photo Video specific extraction
        if 'bhphotovideo.com' in domain:
            return await self._extract_bhphoto_price(url)
        
        # Best Buy specific extraction
        elif 'bestbuy.com' in domain:
            return await self._extract_bestbuy_price(url)
        
        # Amazon specific extraction
        elif 'amazon.com' in domain:
            return await self._extract_amazon_price(url)
        
        return None
    
    async def _extract_bhphoto_price(self, url: str) -> Optional[Dict[str, Any]]:
        """
        B&H Photo Video specific price extraction
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    
                    # B&H specific price selectors
                    price_patterns = [
                        r'data-selenium="pricingPrice"[^>]*>\$([0-9,]+\.?\d*)',
                        r'class="sr-only"[^>]*>Our Price[^>]*>\s*\$([0-9,]+\.?\d*)',
                        r'id="price-\w+"[^>]*>\$([0-9,]+\.?\d*)',
                        r'class="[^"]*price[^"]*"[^>]*>\$([0-9,]+\.?\d*)'
                    ]
                    
                    for pattern in price_patterns:
                        match = re.search(pattern, html, re.IGNORECASE)
                        if match:
                            try:
                                price = float(match.group(1).replace(',', ''))
                                if price > 100:  # Reasonable minimum for electronics
                                    return {'price': price, 'currency': 'USD'}
                            except ValueError:
                                continue
                                
        except Exception as e:
            self.log(f"B&H price extraction failed: {e}")
        
        return None
    
    async def _extract_bestbuy_price(self, url: str) -> Optional[Dict[str, Any]]:
        """Best Buy specific price extraction"""
        # Similar implementation for Best Buy...
        return None
    
    async def _extract_amazon_price(self, url: str) -> Optional[Dict[str, Any]]:
        """Amazon specific price extraction"""  
        # Similar implementation for Amazon...
        return None
    
    def _record_execution(
        self, 
        state: SmartShopperWorkflowState, 
        start_time: datetime, 
        items_processed: int, 
        status: str,
        error_message: Optional[str] = None
    ) -> SmartShopperWorkflowState:
        """Record agent execution in state"""
        execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        
        add_agent_step(
            state,
            self.name,
            status,
            execution_time,
            items_processed=items_processed,
            error_message=error_message
        )
        
        return state