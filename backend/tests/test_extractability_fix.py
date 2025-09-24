#!/usr/bin/env python3
"""
Quick test to verify extractability scoring fix
"""
import sys
import os
sys.path.append('.')

from app.agents.credibility_filter_agent import CredibilityFilterAgent

def test_extractability_scoring():
    """Test the improved extractability scoring logic"""
    agent = CredibilityFilterAgent()
    
    # Test cases
    test_cases = [
        {
            "name": "No content",
            "url": "https://example.com/1",
            "lookup": {"https://example.com/1": {"content": "No content"}},
            "expected_min": 0.1,
            "expected_max": 0.1
        },
        {
            "name": "Empty content", 
            "url": "https://example.com/2",
            "lookup": {"https://example.com/2": {"content": ""}},
            "expected_min": 0.1,
            "expected_max": 0.1
        },
        {
            "name": "Short content",
            "url": "https://example.com/3", 
            "lookup": {"https://example.com/3": {"content": "Short product description"}},
            "expected_min": 0.4,
            "expected_max": 0.6
        },
        {
            "name": "Rich structured content",
            "url": "https://example.com/4",
            "lookup": {"https://example.com/4": {"content": "Gaming laptop with Intel processor, 16GB RAM, RTX 4070 graphics card, 1TB storage, 15.6 inch display, high-performance specs for gaming, price $1299, features advanced cooling, premium build quality, excellent review ratings from customers"}},
            "expected_min": 0.8,
            "expected_max": 1.0
        },
        {
            "name": "Moderate content",
            "url": "https://example.com/5",
            "lookup": {"https://example.com/5": {"content": "Product specifications include good features and competitive price point. Model has decent build quality and customer reviews are generally positive."}},
            "expected_min": 0.5,
            "expected_max": 0.8
        }
    ]
    
    print("🧪 Testing Extractability Scoring Fix:")
    print("=" * 50)
    
    all_passed = True
    
    for test_case in test_cases:
        score = agent._calculate_extractability_score(test_case["url"], test_case["lookup"])
        
        passed = test_case["expected_min"] <= score <= test_case["expected_max"]
        status = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"{status} {test_case['name']}: {score:.3f} (expected: {test_case['expected_min']:.1f}-{test_case['expected_max']:.1f})")
        
        if not passed:
            all_passed = False
            content = test_case["lookup"][test_case["url"]].get("content", "")
            print(f"     Content: '{content[:100]}...' (length: {len(content)})")
    
    print(f"\n🎯 Overall Result: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    return all_passed

if __name__ == "__main__":
    success = test_extractability_scoring()
    sys.exit(0 if success else 1)