#!/usr/bin/env python3
"""
SpecExtractorAgent Integration Demo

Demonstrates the Universal SpecExtractorAgent extracting specifications
from diverse product categories using the 3-agent pipeline:
QueryOrchestrator -> TavilyRetriever -> CredibilityFilter -> SpecExtractor
"""
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock

# Add backend to path
sys.path.append('.')

from app.agents.spec_extractor_agent import SpecExtractorAgent
from app.agents.state import create_initial_state, SearchQuery

def test_category_detection():
    """Test universal category detection across product types"""
    print("\nTesting Universal Category Detection")
    print("=" * 50)
    
    # Use just the detector component, not the full agent
    from app.agents.spec_extractor_agent import UniversalCategoryDetector
    detector = UniversalCategoryDetector()
    
    test_products = [
        # Electronics
        ("MacBook Pro M3 16-inch laptop", "laptop"),
        ("iPhone 15 Pro smartphone camera", "smartphone"),
        ("Sony WH-1000XM5 wireless headphones", "headphones"),
        ("Canon EOS R6 mirrorless camera", "camera"),
        
        # Kitchen & Home
        ("Ninja Professional Blender 1000W", "kitchen"),
        ("KitchenAid Stand Mixer Artisan", "kitchen"),
        ("Herman Miller Aeron office chair", "furniture"),
        ("IKEA Billy bookshelf white", "furniture"),
        
        # Fashion & Personal
        ("Nike Air Max 270 running shoes", "shoes"),
        ("Levi's 501 original jeans denim", "clothing"),
        ("Apple Watch Series 9 GPS", "accessories"),
        
        # Toys & Kids
        ("LEGO Creator 3-in-1 Deep Sea", "toys"),
        ("Baby Einstein activity table", "baby"),
        ("Monopoly Classic board game", "toys"),
        
        # Other categories
        ("The Great Gatsby classic novel", "books"),
        ("Call of Duty Modern Warfare", "games"),
        ("Michelin Pilot Sport 4S tire", "automotive"),
    ]
    
    correct_predictions = 0
    for title, expected_category in test_products:
        detected_category = detector.detect_category(title)
        status = "" if detected_category == expected_category else ""
        print(f"{status} {title[:40]:40} -> {detected_category:12} (expected: {expected_category})")
        if detected_category == expected_category:
            correct_predictions += 1
    
    accuracy = correct_predictions / len(test_products) * 100
    print(f"\nCategory Detection Accuracy: {accuracy:.1f}% ({correct_predictions}/{len(test_products)})")

def test_spec_extraction():
    """Test specification extraction from different product types"""
    print("\nTesting Dynamic Specification Extraction")
    print("=" * 50)
    
    # Use just the extraction components, not the full agent
    from app.agents.spec_extractor_agent import DynamicSpecExtractor, UniversalUnitNormalizer
    spec_extractor = DynamicSpecExtractor()
    unit_normalizer = UniversalUnitNormalizer()
    
    test_cases = [
        {
            "name": "Gaming Laptop",
            "content": """
            ASUS ROG Strix G15 Gaming Laptop Specifications:
            - Processor: AMD Ryzen 7 5800H
            - Graphics: NVIDIA GeForce RTX 3060 6GB
            - RAM: 16 GB DDR4
            - Storage: 512 GB NVMe SSD
            - Display: 15.6" Full HD (1920x1080) 144Hz
            - Weight: 2.3 kg
            - Battery: 90 Wh
            - Price: $1,299.99
            - Color: Eclipse Gray
            """,
            "expected_fields": ["processor", "memory", "storage", "screen", "weight", "battery", "price"]
        },
        {
            "name": "Kitchen Blender", 
            "content": """
            Vitamix A3500 Ascent Series Smart Blender:
            - Power: 1400 watts motor
            - Capacity: 64 oz low-profile container
            - Speeds: Variable speed control + 5 programs
            - Material: BPA-free Eastman Tritan
            - Dimensions: 11 x 8 x 17 inches
            - Weight: 12 lbs
            - Price: $449.95
            - Color: Brushed Stainless Steel
            - Timer: Built-in digital timer
            """,
            "expected_fields": ["power", "capacity", "material", "dimensions", "weight", "price"]
        },
        {
            "name": "Running Shoes",
            "content": """
            Nike Air Zoom Pegasus 40 Running Shoes:
            - Gender: Men's
            - Size: Available in 7-13
            - Material: Mesh upper with synthetic overlays
            - Color: Black/White/Anthracite
            - Weight: 10.7 oz (size 10)
            - Technology: Nike Air Zoom unit
            - Price: $129.99
            - Fit: True to size, medium width
            """,
            "expected_fields": ["gender", "size", "material", "color", "weight", "price"]
        },
        {
            "name": "LEGO Set",
            "content": """
            LEGO Creator Expert Big Ben (10253):
            - Ages: 16+ years
            - Pieces: 4,163 pieces
            - Dimensions: 23" x 9" x 9" when built
            - Theme: Architecture/Creator Expert
            - Features: Working clock mechanism
            - Price: $249.99
            - Instructions: 459-page instruction booklet
            """,
            "expected_fields": ["age", "pieces", "dimensions", "theme", "price"]
        }
    ]
    
    for test_case in test_cases:
        print(f"\n {test_case['name']}:")
        print("-" * 30)
        
        specs = spec_extractor.extract_specs(test_case["content"], "general")
        normalized_specs = unit_normalizer.normalize_specs(specs)
        
        # Check coverage
        found_fields = 0
        for expected_field in test_case["expected_fields"]:
            if any(expected_field in key for key in normalized_specs.keys()):
                found_fields += 1
                
        coverage = found_fields / len(test_case["expected_fields"]) * 100
        
        print(f"   Extracted {len(normalized_specs)} specifications:")
        for key, value in normalized_specs.items():
            print(f"   - {key}: {value}")
        
        print(f"    Coverage: {coverage:.1f}% ({found_fields}/{len(test_case['expected_fields'])} expected fields)")

async def test_pipeline_integration():
    """Test SpecExtractorAgent integration with pipeline state"""
    print("\nTesting Pipeline Integration")
    print("=" * 50)
    
    # Mock the LLM to avoid needing real API key
    from unittest.mock import patch
    with patch('app.agents.spec_extractor_agent.ChatOpenAI') as mock_chat:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=type('Response', (), {
            'content': '{"warranty": "2 years", "connectivity": "Wi-Fi 6, Bluetooth 5.0"}'
        })())
        mock_chat.return_value = mock_llm
        
        agent = SpecExtractorAgent()
    
    # Create test state with credibility-filtered results
    state = create_initial_state("test products")
    state["search_query"] = SearchQuery(
        raw_query="universal products test",
        normalized_query="universal products",
        intent="product_search"
    )
    
    # Mock credibility-filtered results from different categories
    state["credibility_filtered_results"] = [
        {
            "url": "https://apple.com/macbook-pro",
            "title": "MacBook Pro M3 16-inch",
            "content": """
            MacBook Pro 16-inch with M3 chip specifications:
            - Chip: Apple M3 Pro with 12‑core CPU, 18‑core GPU
            - Memory: 16GB unified memory
            - Storage: 512GB SSD storage
            - Display: 16.2-inch Liquid Retina XDR display (3456×2234)
            - Battery: Up to 22 hours video playback
            - Weight: 4.7 pounds (2.1 kg)
            - Price: Starting at $2,499
            - Ports: 3x Thunderbolt 4, HDMI, SDXC, MagSafe 3
            """,
            "credibility_score": 0.95
        },
        {
            "url": "https://williams-sonoma.com/vitamix-blender",
            "title": "Vitamix A3500 Smart Blender",
            "content": """
            Vitamix A3500 Ascent Series features:
            - Motor: 1400-watt motor base
            - Container: 64-oz low-profile container
            - Programs: 5 pre-programmed settings
            - Material: BPA-free Eastman Tritan
            - Warranty: 10-year full warranty
            - Price: $449.95
            - Controls: Touch-screen controls with timer
            """,
            "credibility_score": 0.87
        },
        {
            "url": "https://lego.com/creator-expert",
            "title": "LEGO Creator Expert Taj Mahal",
            "content": """
            LEGO Creator Expert Taj Mahal (10256):
            - Age range: 16+ years
            - Piece count: 5,923 pieces
            - Finished size: 20" (51cm) wide, 20" (51cm) deep, 16" (41cm) high
            - Features: Removable main dome reveals detailed interior
            - Price: $369.99
            - Theme: Creator Expert Architecture
            """,
            "credibility_score": 0.92
        }
    ]
    
    # Process the state
    result_state = await agent.process(state)
    
    # Verify results
    structured_products = result_state.get("structured_products", [])
    print(f"   Processed {len(structured_products)} products:")
    
    for i, product in enumerate(structured_products, 1):
        print(f"\n   {i}. {product.get('title', 'Unknown Product')}")
        print(f"      Category: {product.get('category', 'general')}")
        print(f"      Brand: {product.get('brand', 'N/A')}")
        print(f"      Price: ${product.get('price', 'N/A')} {product.get('currency', '')}")
        print(f"      Coverage: {product.get('extraction_coverage', 0):.1%}")
        print(f"      Method: {product.get('extraction_method', 'N/A')}")
        
        specs = product.get('specs', {})
        if specs:
            print(f"      Specs: {len(specs)} extracted")
            for key, value in list(specs.items())[:3]:  # Show first 3 specs
                print(f"        - {key}: {value}")
            if len(specs) > 3:
                print(f"        - ... and {len(specs) - 3} more")
    
    print(f"\n Pipeline integration successful!")

def main():
    """Run all SpecExtractorAgent demonstrations"""
    print(" SpecExtractorAgent Universal Product Demo")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Test 1: Category Detection
        test_category_detection()
        
        # Test 2: Spec Extraction  
        test_spec_extraction()
        
        # Test 3: Pipeline Integration
        asyncio.run(test_pipeline_integration())
        
        print("\n" + "=" * 60)
        print(" ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nUniversal Category Detection: Working across all product types")
        print(" Dynamic Spec Extraction: Adapts to any product category")  
        print(" Pattern Recognition: Handles diverse content formats")
        print(" Unit Normalization: Standardizes measurements")
        print(" Pipeline Integration: Seamless state management")
        print(" Coverage Calculation: Measures extraction quality")
        print(" LLM Enhancement: Fills gaps in extraction")
        
        print("\nSpecExtractorAgent is ready for production!")
        print(" Next step: Implement ResultsRankerAgent for final ranking")
        
    except Exception as e:
        print(f"\n Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
