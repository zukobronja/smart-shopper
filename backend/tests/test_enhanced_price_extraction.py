"""
Tests for enhanced RSS price extraction
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.rss.price_extractor import EnhancedRSSPriceExtractor, extract_enhanced_price


class TestEnhancedRSSPriceExtractor:
    """Test the enhanced price extraction functionality"""
    
    def setup_method(self):
        self.extractor = EnhancedRSSPriceExtractor()
    
    def test_metadata_extraction_basic_price(self):
        """Test extraction from RSS metadata fields"""
        entry = {
            "price": "99.99",
            "currency": "USD",
            "title": "Test Product"
        }
        
        price, currency = self.extractor._extract_from_metadata(entry)
        assert price == 99.99
        assert currency == "USD"
    
    def test_metadata_extraction_g_commerce(self):
        """Test extraction from Google Shopping RSS fields"""
        entry = {
            "g:price": "149.50",
            "g:currency": "EUR",
            "title": "Test Product"
        }
        
        price, currency = self.extractor._extract_from_metadata(entry)
        assert price == 149.50
        assert currency == "EUR"
    
    def test_metadata_extraction_nested_data(self):
        """Test extraction from nested RSS data structures"""
        entry = {
            "title": "Test Product",
            "product_info": {
                "sale_price": "75.00",
                "price_currency": "GBP"
            }
        }
        
        price, currency = self.extractor._extract_from_metadata(entry)
        assert price == 75.00
        assert currency == "GBP"
    
    def test_text_extraction_dollar_symbol(self):
        """Test price extraction from text with dollar symbol"""
        text = "Great deal on this laptop for only $899.99! Limited time offer."
        
        price, currency = self.extractor._extract_from_text(text)
        assert price == 899.99
        assert currency == "USD"
    
    def test_text_extraction_euro_symbol(self):
        """Test price extraction from text with euro symbol"""
        text = "Premium headphones available for €129.50 with free shipping."
        
        price, currency = self.extractor._extract_from_text(text)
        assert price == 129.50
        assert currency == "EUR"
    
    def test_text_extraction_currency_code(self):
        """Test price extraction from text with currency codes"""
        text = "Special price: 1299 USD for this gaming setup"
        
        price, currency = self.extractor._extract_from_text(text)
        assert price == 1299.0
        assert currency == "USD"
    
    def test_text_extraction_deal_patterns(self):
        """Test extraction of deal-specific patterns"""
        text = "Was $199.99, now $149.99! Save $50 on this amazing product"
        
        price, currency = self.extractor._extract_from_text(text)
        # Should prefer 'now' price over 'was' price
        assert price == 149.99
        assert currency == "USD"
    
    def test_text_extraction_international_currencies(self):
        """Test extraction of various international currencies"""
        test_cases = [
            ("Price: ¥5999 for this item", 5999.0, "JPY"),
            ("Cost ₹12,500 with delivery", 12500.0, "INR"),
            ("Special offer: ₪299.90", 299.90, "ILS"),
            ("Sale price 1250 AED", 1250.0, "AED"),
            ("Only C$89.99 today", 89.99, "CAD"),
        ]
        
        for text, expected_price, expected_currency in test_cases:
            price, currency = self.extractor._extract_from_text(text)
            assert price == expected_price, f"Failed for text: {text}"
            assert currency == expected_currency, f"Failed for text: {text}"
    
    def test_should_scrape_link_allowed_domain(self):
        """Test that allowed domains are approved for scraping"""
        allowed_links = [
            "https://bestbuy.com/product/123",
            "https://newegg.com/deals",
            "https://microcenter.com/product/456"
        ]
        
        for link in allowed_links:
            assert self.extractor._should_scrape_link(link) == True
    
    def test_should_scrape_link_blocked_domain(self):
        """Test that blocked domains are rejected for scraping"""
        blocked_links = [
            "https://amazon.com/dp/B123456789",
            "https://walmart.com/ip/123456789",
            "https://target.com/p/A-123456789",
            "https://amazon.co.uk/dp/B123456789"
        ]
        
        for link in blocked_links:
            assert self.extractor._should_scrape_link(link) == False
    
    def test_parse_price_from_html(self):
        """Test HTML price parsing with common selectors"""
        html = """
        <html>
            <body>
                <div class="price">$299.99</div>
                <span class="original-price">$399.99</span>
            </body>
        </html>
        """
        
        price, currency = self.extractor._parse_price_from_html(html)
        assert price == 299.99
        assert currency == "USD"
    
    @pytest.mark.asyncio
    async def test_extract_price_metadata_priority(self):
        """Test that metadata extraction has priority over text extraction"""
        entry = {
            "title": "Product costs $500",  # Text extraction would find this
            "summary": "Great product for $400",  # Text extraction would find this
            "price": "99.99",  # Metadata should take priority
            "currency": "USD"
        }
        
        price, currency = await self.extractor.extract_price(entry)
        assert price == 99.99  # Should use metadata, not text
        assert currency == "USD"
    
    @pytest.mark.asyncio
    async def test_extract_price_text_fallback(self):
        """Test fallback to text extraction when metadata is not available"""
        entry = {
            "title": "Amazing laptop",
            "summary": "Get this laptop for only €899.50 with free shipping!",
            "link": "https://example.com/laptop"
        }
        
        price, currency = await self.extractor.extract_price(entry)
        assert price == 899.50
        assert currency == "EUR"
    
    @pytest.mark.asyncio 
    async def test_extract_price_no_price_found(self):
        """Test behavior when no price is found anywhere"""
        entry = {
            "title": "Some product",
            "summary": "A great product with amazing features",
            "link": "https://example.com/product"
        }
        
        price, currency = await self.extractor.extract_price(entry)
        assert price is None
        assert currency is None
    
    def test_extract_from_text_price_range_validation(self):
        """Test that prices are within reasonable range"""
        # Test extremely low price (should be rejected)
        text = "Only $0.01 for this product"
        price, currency = self.extractor._extract_from_text(text)
        assert price is None  # Below minimum threshold
        
        # Test extremely high price (should be rejected)  
        text = "Premium item for $9999999"
        price, currency = self.extractor._extract_from_text(text)
        assert price is None  # Above maximum threshold
        
        # Test normal price (should be accepted)
        text = "Great deal at $299.99"
        price, currency = self.extractor._extract_from_text(text)
        assert price == 299.99
        assert currency == "USD"


@pytest.mark.asyncio
async def test_extract_enhanced_price_convenience_function():
    """Test the convenience function for RSS worker integration"""
    entry = {
        "title": "Test Product",
        "summary": "Special price: $149.99",
        "link": "https://example.com"
    }
    
    price, currency = await extract_enhanced_price(entry)
    assert price == 149.99
    assert currency == "USD"


if __name__ == "__main__":
    # Run a quick test
    async def quick_test():
        entry = {
            "title": "Gaming Laptop",
            "summary": "Powerful gaming laptop now available for €1,299.99!",
            "price": "1299.99",
            "currency": "EUR"
        }
        
        price, currency = await extract_enhanced_price(entry)
        print(f"Extracted: {price} {currency}")
        assert price == 1299.99
        assert currency == "EUR"
        print("✅ Quick test passed!")
    
    asyncio.run(quick_test())