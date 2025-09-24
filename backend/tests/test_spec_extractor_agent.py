#!/usr/bin/env python3
"""
Unit Tests for SpecExtractorAgent

Tests the universal product specification extraction across all categories:
- Category detection for diverse product types
- Dynamic specification extraction patterns
- LLM enhancement for missing fields
- Universal unit normalization
- Coverage calculation accuracy
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.spec_extractor_agent import (
    SpecExtractorAgent, 
    UniversalCategoryDetector, 
    DynamicSpecExtractor,
    UniversalUnitNormalizer
)
from app.agents.state import create_initial_state, SearchQuery


class TestUniversalCategoryDetector:
    """Test category detection across diverse product types"""
    
    def setup_method(self):
        self.detector = UniversalCategoryDetector()
    
    def test_electronics_detection(self):
        """Test detection of electronics categories"""
        test_cases = [
            ("MacBook Pro 16-inch laptop", "laptop"),
            ("iPhone 15 Pro smartphone", "smartphone"),
            ("Sony WH-1000XM5 headphones", "headphones"),
            ("iPad Air tablet", "tablet"),
            ("Dell 27-inch 4K monitor", "monitor"),
            ("Gaming mechanical keyboard", "keyboard"),
            ("Canon EOS R6 camera", "camera"),
        ]
        
        for title, expected_category in test_cases:
            category = self.detector.detect_category(title)
            assert category == expected_category, f"Expected {expected_category}, got {category} for '{title}'"
    
    def test_kitchen_home_detection(self):
        """Test detection of kitchen and home categories"""
        test_cases = [
            ("Ninja Professional Blender", "kitchen"),
            ("KitchenAid Stand Mixer", "kitchen"),
            ("Breville Smart Toaster", "kitchen"),
            ("Dyson V15 Vacuum Cleaner", "appliance"),
            ("Herman Miller Aeron Chair", "furniture"),
            ("IKEA Malm Dresser", "furniture"),
            ("Philips Hue Smart Lamp", "home_decor"),
        ]
        
        for title, expected_category in test_cases:
            category = self.detector.detect_category(title)
            assert category == expected_category, f"Expected {expected_category}, got {category} for '{title}'"
    
    def test_fashion_personal_detection(self):
        """Test detection of fashion and personal care categories"""
        test_cases = [
            ("Nike Dri-FIT Running Shirt", "clothing"),
            ("Levi's 501 Original Jeans", "clothing"),
            ("Adidas Ultraboost 22 Running Shoes", "shoes"),
            ("Apple Watch Series 9", "accessories"),
            ("L'Oreal Revitalift Skincare Set", "beauty"),
            ("Gillette Fusion5 Razor", "personal_care"),
        ]
        
        for title, expected_category in test_cases:
            category = self.detector.detect_category(title)
            assert category == expected_category, f"Expected {expected_category}, got {category} for '{title}'"
    
    def test_toys_kids_detection(self):
        """Test detection of toys and kids categories"""
        test_cases = [
            ("LEGO Creator 3-in-1 Deep Sea Creatures", "toys"),
            ("Barbie Dreamhouse Dollhouse", "toys"),
            ("Baby Einstein Activity Table", "baby"),
            ("Fisher-Price Rock 'n Play", "baby"),
            ("Monopoly Board Game", "toys"),
        ]
        
        for title, expected_category in test_cases:
            category = self.detector.detect_category(title)
            assert category == expected_category, f"Expected {expected_category}, got {category} for '{title}'"
    
    def test_automotive_books_detection(self):
        """Test detection of automotive and books categories"""
        test_cases = [
            ("Michelin Pilot Sport 4S Tire", "automotive"),
            ("Optima RedTop Car Battery", "automotive"),
            ("The Great Gatsby Novel", "books"),
            ("Python Programming Textbook", "books"),
            ("Call of Duty: Modern Warfare", "games"),
        ]
        
        for title, expected_category in test_cases:
            category = self.detector.detect_category(title)
            assert category == expected_category, f"Expected {expected_category}, got {category} for '{title}'"
    
    def test_unknown_category_fallback(self):
        """Test fallback to 'general' for unknown products"""
        unknown_title = "Quantum Flux Capacitor Widget"
        category = self.detector.detect_category(unknown_title)
        assert category == "general"


class TestDynamicSpecExtractor:
    """Test dynamic specification extraction patterns"""
    
    def setup_method(self):
        self.extractor = DynamicSpecExtractor()
    
    def test_universal_pattern_extraction(self):
        """Test universal patterns that work across categories"""
        content = """
        Product Details:
        - Dimensions: 12.5 x 8.2 x 0.6 inches
        - Weight: 3.2 lbs
        - Color: Space Gray
        - Material: Aluminum
        - Power: 65 watts
        - Capacity: 512 GB
        """
        
        specs = self.extractor.extract_specs(content, "general")
        
        assert "dimensions" in specs
        assert "12.5×8.2×0.6 inches" in specs["dimensions"]
        assert "weight" in specs
        assert "3.2 lbs" in specs["weight"]
        assert "color" in specs
        assert "space gray" in specs["color"].lower()
        assert "material" in specs
        assert "aluminum" in specs["material"].lower()
        assert "power" in specs
        assert "65 watts" in specs["power"]
    
    def test_electronics_specific_extraction(self):
        """Test electronics-specific pattern extraction"""
        content = """
        Technical Specifications:
        - Processor: Intel Core i7-12700H
        - RAM: 16 GB DDR4
        - Storage: 512 GB SSD
        - Display: 15.6" 1920x1080
        - Graphics: NVIDIA RTX 3060
        - Battery: 80 Wh
        """
        
        specs = self.extractor.extract_specs(content, "laptop")
        
        assert "memory" in specs
        assert "16 GB" in specs["memory"]
        assert "screen" in specs
        assert "15.6" in specs["screen"]
        assert "resolution" in specs
        assert "1920×1080" in specs["resolution"]
        assert "battery" in specs
        assert "80 Wh" in specs["battery"]
        assert "processor" in specs
        assert "intel" in specs["processor"].lower()
    
    def test_kitchen_specific_extraction(self):
        """Test kitchen appliance pattern extraction"""
        content = """
        Features:
        - Capacity: 64 oz pitcher
        - Power: 1400 watts
        - Speeds: 10 variable speeds
        - Timer: 60 minute auto-shutoff
        - Material: BPA-free plastic
        """
        
        specs = self.extractor.extract_specs(content, "kitchen")
        
        assert "capacity" in specs
        assert "64 oz" in specs["capacity"]
        assert "power" in specs
        assert "1400 watts" in specs["power"]
        assert "speeds" in specs
        assert specs["speeds"] == 10
        assert "timer" in specs
        assert "60 minute" in specs["timer"]
    
    def test_clothing_specific_extraction(self):
        """Test clothing pattern extraction"""
        content = """
        Product Info:
        - Size: Large
        - Fit: Slim fit
        - Material: 100% Cotton
        - Gender: Men's
        - Color: Navy Blue
        """
        
        specs = self.extractor.extract_specs(content, "clothing")
        
        assert "size" in specs
        assert "large" in specs["size"].lower()
        assert "fit" in specs
        assert "slim" in specs["fit"]
        assert "gender" in specs
        assert "men" in specs["gender"].lower()
        assert "material" in specs
        assert "cotton" in specs["material"].lower()
    
    def test_toys_specific_extraction(self):
        """Test toy pattern extraction"""
        content = """
        Product Details:
        - Ages: 8+
        - Pieces: 1,023 pieces
        - Theme: Star Wars
        - Players: 1-4 players
        - Dimensions: 20 x 15 x 12 inches
        """
        
        specs = self.extractor.extract_specs(content, "toys")
        
        assert "age" in specs
        assert "8+" in specs["age"]
        assert "pieces" in specs
        assert "1,023 pieces" in specs["pieces"]
        assert "theme" in specs
        assert "Star Wars" in specs["theme"]
        assert "players" in specs
        assert "1-4" in specs["players"]


class TestUniversalUnitNormalizer:
    """Test universal unit normalization"""
    
    def setup_method(self):
        self.normalizer = UniversalUnitNormalizer()
    
    def test_weight_normalization(self):
        """Test weight unit normalization to kg"""
        specs = {
            "weight_1": "5.5 lbs",
            "weight_2": "2500 grams",
            "weight_3": "16 oz",
            "weight_4": "1.2 kg"
        }
        
        normalized = self.normalizer.normalize_specs(specs)
        
        # 5.5 lbs ≈ 2.49 kg
        assert "2.49 kg" in normalized["weight_1"]
        # 2500 grams = 2.5 kg
        assert "2.50 kg" in normalized["weight_2"]
        # 16 oz ≈ 0.45 kg
        assert "0.45" in normalized["weight_3"]
        # Already kg
        assert "1.2 kg" in normalized["weight_4"]
    
    def test_memory_normalization(self):
        """Test memory/storage normalization to GB"""
        specs = {
            "memory_1": "16 GB",
            "storage_1": "1 TB",
            "ram_1": "8192 MB"
        }
        
        normalized = self.normalizer.normalize_specs(specs)
        
        assert "16 GB" in normalized["memory_1"]  # Already GB
        assert "1024 GB" in normalized["storage_1"]  # 1 TB = 1024 GB
        assert "8 GB" in normalized["ram_1"]  # 8192 MB = 8 GB
    
    def test_dimension_normalization(self):
        """Test dimension normalization to inches"""
        specs = {
            "dimensions_1": "30×20×10 cm",
            "dimensions_2": "12×8×2 inches"
        }
        
        normalized = self.normalizer.normalize_specs(specs)
        
        # 30 cm ≈ 11.8 inches
        assert "11.8" in normalized["dimensions_1"]
        assert "inches" in normalized["dimensions_1"]
        # Already inches
        assert "12×8×2 inches" in normalized["dimensions_2"]


@pytest.mark.asyncio
class TestSpecExtractorAgent:
    """Test the main SpecExtractorAgent functionality"""
    
    @patch('app.agents.spec_extractor_agent.ChatOpenAI')
    def setup_method(self, mock_chat_openai):
        # Mock the LLM to avoid needing real API keys
        mock_llm = AsyncMock()
        mock_chat_openai.return_value = mock_llm
        self.agent = SpecExtractorAgent()
    
    async def test_agent_initialization(self):
        """Test agent initialization"""
        assert self.agent.name == "Spec Extractor"
        assert self.agent.color == self.agent.YELLOW
        assert self.agent.category_detector is not None
        assert self.agent.spec_extractor is not None
        assert self.agent.unit_normalizer is not None
        assert self.agent.llm is not None
    
    async def test_basic_info_extraction(self):
        """Test basic product information extraction"""
        result = {
            "url": "https://example.com/product",
            "title": "Apple MacBook Pro 16-inch",
            "content": "Price: $2,499 USD. In stock. Ships within 2 days."
        }
        
        basic_info = self.agent._extract_basic_info(result)
        
        assert basic_info["title"] == "Apple MacBook Pro 16-inch"
        assert basic_info["brand"] == "Apple"
        assert basic_info["price"] == 2499.0
        assert basic_info["currency"] == "USD"
    
    async def test_price_extraction_patterns(self):
        """Test various price format extraction"""
        test_cases = [
            ("Price: $99.99", 99.99, "USD"),
            ("€249.50 EUR", 249.50, "EUR"),
            ("£199 GBP", 199.0, "GBP"),
            ("Cost: 1,299 dollars", 1299.0, "USD"),
        ]
        
        for content, expected_price, expected_currency in test_cases:
            price_info = self.agent._extract_price_info(content)
            assert price_info.get("price") == expected_price
            assert price_info.get("currency") == expected_currency
    
    async def test_coverage_calculation(self):
        """Test coverage calculation for different categories"""
        # High coverage laptop
        basic_info = {
            "title": "Dell XPS 13",
            "brand": "Dell",
            "price": 999.0,
            "currency": "USD"
        }
        specs = {
            "processor": "Intel i7",
            "memory": "16 GB",
            "storage": "512 GB",
            "screen": "13.3 inches"
        }
        
        coverage = self.agent._calculate_coverage(basic_info, specs, "laptop")
        assert coverage >= 0.8  # Should be high coverage
        
        # Low coverage general product
        basic_info_low = {"title": "Mystery Product"}
        specs_low = {}
        
        coverage_low = self.agent._calculate_coverage(basic_info_low, specs_low, "general")
        assert coverage_low < 0.7  # Should be lower coverage
    
    async def test_process_with_mock_data(self):
        """Test main process method with mock credibility results"""
        # Create test state with credibility results
        state = create_initial_state("test laptop")
        state["search_query"] = SearchQuery(
            raw_query="test laptop",
            normalized_query="test laptop",
            intent="product_search",
            category="laptop"
        )
        
        # Mock credibility results
        state["credibility_filtered_results"] = [
            {
                "url": "https://dell.com/xps13",
                "title": "Dell XPS 13 Laptop",
                "content": """
                Dell XPS 13 Specifications:
                - Processor: Intel Core i7-1265U
                - RAM: 16 GB LPDDR5
                - Storage: 512 GB SSD
                - Display: 13.4" FHD+ (1920x1200)
                - Weight: 2.64 lbs
                - Battery: 52 Wh
                - Price: $1,199.99
                - Color: Platinum Silver
                - Material: Aluminum
                """,
                "credibility_score": 0.85
            },
            {
                "url": "https://amazon.com/ninja-blender",
                "title": "Ninja Professional Blender",
                "content": """
                Ninja BL610 Professional Blender Features:
                - Power: 1000 watts
                - Capacity: 72 oz pitcher
                - Speeds: Variable speed control
                - Material: BPA-free plastic
                - Dimensions: 9.5 x 7.5 x 17 inches
                - Weight: 9 lbs
                - Price: $79.99
                - Color: Black
                """,
                "credibility_score": 0.75
            }
        ]
        
        # Mock LLM to avoid real API calls
        with patch.object(self.agent, 'llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=type('Response', (), {
                'content': '{"warranty": "1 year", "ports": "USB-C, Thunderbolt"}'
            })())
            
            # Process the state
            result_state = await self.agent.process(state)
        
        # Verify results
        assert "structured_products" in result_state
        structured_products = result_state["structured_products"]
        assert len(structured_products) == 2
        
        # Check laptop extraction
        laptop = structured_products[0]
        assert laptop["title"] == "Dell XPS 13 Laptop"
        assert laptop["brand"] == "Dell"
        assert laptop["category"] == "laptop"
        assert laptop["price"] == 1199.99
        assert laptop["currency"] == "USD"
        assert "processor" in laptop["specs"]
        assert "memory" in laptop["specs"]
        assert laptop["extraction_coverage"] > 0.6
        
        # Check blender extraction
        blender = structured_products[1]
        assert blender["title"] == "Ninja Professional Blender"
        assert blender["brand"] == "Ninja"
        assert blender["category"] == "kitchen"
        assert blender["price"] == 79.99
        assert "power" in blender["specs"]
        assert "capacity" in blender["specs"]
    
    async def test_empty_results_handling(self):
        """Test handling of empty credibility results"""
        state = create_initial_state("test query")
        state["credibility_filtered_results"] = []
        
        result_state = await self.agent.process(state)
        
        assert result_state["structured_products"] == []
        assert len(result_state["agent_steps"]) == 1
        assert result_state["agent_steps"][0].status == "success"
    
    async def test_error_handling(self):
        """Test error handling in processing"""
        state = create_initial_state("test query")
        # Invalid credibility results to trigger error
        state["credibility_filtered_results"] = [{"invalid": "data"}]
        
        result_state = await self.agent.process(state)
        
        # Should handle gracefully
        assert "structured_products" in result_state
        assert len(result_state["agent_steps"]) == 1
    
    def test_llm_prompt_creation(self):
        """Test LLM prompt creation for different categories"""
        content = "Sample product content"
        category = "laptop"
        existing_specs = {"memory": "16 GB"}
        
        prompt = self.agent._create_extraction_prompt(content, category, existing_specs)
        
        assert "laptop" in prompt
        assert "processor" in prompt  # Should include laptop-specific hints
        assert "memory" in prompt  # Should mention existing specs
        assert "JSON" in prompt  # Should request JSON format
    
    def test_llm_spec_validation(self):
        """Test LLM specification validation"""
        llm_specs = {
            "processor": "Intel i7",
            "invalid spec!": "bad value",
            "": "empty key",
            "good_spec": "good value",
            "duplicate": "value"
        }
        existing_specs = {"duplicate": "existing"}
        
        validated = self.agent._validate_llm_specs(llm_specs, existing_specs)
        
        assert "processor" in validated
        assert "good_spec" in validated
        assert "invalid_spec" not in validated  # Should clean bad characters
        assert "duplicate" not in validated  # Should skip existing
        assert "" not in validated  # Should skip empty keys


if __name__ == "__main__":
    # Run specific test for debugging
    pytest.main([__file__, "-v"])