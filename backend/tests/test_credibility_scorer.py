"""
Unit tests for credibility scoring system
Tests domain reputation, recency, extractability, and content quality scoring
"""
import pytest
from datetime import datetime, timedelta, timezone
from app.extractors.credibility_scorer import CredibilityScorer

class TestCredibilityScorer:
    """Test suite for credibility scoring system"""
    
    @classmethod
    def setup_class(cls):
        """Set up test class"""
        cls.scorer = CredibilityScorer()
        
    def test_domain_reputation_scoring(self):
        """Test domain reputation scoring for different tiers"""
        
        # Tier 1 domains (highest trust)
        score = self.scorer._score_domain_reputation("https://www.amazon.com/product/123")
        assert score == 1.0, f"Amazon should get tier 1 score, got {score}"
        
        score = self.scorer._score_domain_reputation("https://www.wirecutter.com/reviews/laptop")
        assert score == 1.0, f"Wirecutter should get tier 1 score, got {score}"
        
        # Tier 2 domains (good trust)
        score = self.scorer._score_domain_reputation("https://www.newegg.com/laptop")
        assert score == 0.80, f"Newegg should get tier 2 score, got {score}"
        
        score = self.scorer._score_domain_reputation("https://www.ikea.com/chair")
        assert score == 0.80, f"IKEA should get tier 2 score, got {score}"
        
        # Tier 3 domains (moderate trust)
        score = self.scorer._score_domain_reputation("https://www.ebay.com/item/123")
        assert score == 0.60, f"eBay should get tier 3 score, got {score}"
        
        # Unknown domain without e-commerce indicators
        score = self.scorer._score_domain_reputation("https://randomsite.com/page")
        assert score == 0.30, f"Unknown domain should get base score, got {score}"
        
        # Unknown domain with e-commerce indicators
        score = self.scorer._score_domain_reputation("https://unknownshop.com/product/laptop")
        assert score == 0.50, f"Unknown e-commerce domain should get boosted score, got {score}"
        
        print("✓ Domain reputation scoring works correctly")
    
    def test_recency_scoring(self):
        """Test recency scoring based on publication dates"""
        
        now = datetime.now(timezone.utc)
        
        # Very recent (1 week)
        recent_data = {
            "review": {
                "published_at": (now - timedelta(days=5)).isoformat() + "Z"
            }
        }
        score = self.scorer._score_recency(recent_data)
        assert score == 1.0, f"Recent content should get max score, got {score}"
        
        # Recent (1 month)
        month_old_data = {
            "review": {
                "published_at": (now - timedelta(days=20)).isoformat() + "Z"
            }
        }
        score = self.scorer._score_recency(month_old_data)
        assert score == 0.90, f"Month-old content should get 0.90, got {score}"
        
        # Moderate (6 months)
        old_data = {
            "review": {
                "published_at": (now - timedelta(days=150)).isoformat() + "Z"
            }
        }
        score = self.scorer._score_recency(old_data)
        assert score == 0.60, f"6-month-old content should get 0.60, got {score}"
        
        # Very old (2+ years)
        very_old_data = {
            "review": {
                "published_at": (now - timedelta(days=800)).isoformat() + "Z"
            }
        }
        score = self.scorer._score_recency(very_old_data)
        assert score == 0.15, f"Very old content should get 0.15, got {score}"
        
        # No date info
        score = self.scorer._score_recency(None)
        assert score == 0.60, f"No date info should get default 0.60, got {score}"
        
        print("✓ Recency scoring works correctly")
    
    def test_extractability_scoring(self):
        """Test extractability scoring based on data structure quality"""
        
        # No data extracted
        score = self.scorer._score_extractability(None)
        assert score == 0.30, f"No data should get low score, got {score}"
        
        # High-quality e-commerce data
        rich_ecom_data = {
            "page_type": "ecom",
            "product": {
                "title": "Gaming Laptop XPS 15",
                "brand": "Dell", 
                "category": "electronics",
                "specs": {
                    "specifications": {
                        "cpu": "Intel i7",
                        "ram_gb": 16,
                        "storage_gb": 512,
                        "screen_size": "15.6 inches"
                    }
                }
            },
            "offer": {
                "price": 1299.99,
                "availability": "in_stock",
                "rating": 4.5
            }
        }
        score = self.scorer._score_extractability(rich_ecom_data)
        assert score >= 0.85, f"Rich e-commerce data should get high score, got {score}"
        
        # Basic e-commerce data
        basic_ecom_data = {
            "page_type": "ecom",
            "product": {
                "title": "Laptop"
            },
            "offer": {}
        }
        score = self.scorer._score_extractability(basic_ecom_data)
        assert 0.40 <= score <= 0.60, f"Basic e-commerce data should get moderate score, got {score}"
        
        # High-quality review data
        rich_review_data = {
            "page_type": "review",
            "review": {
                "headline": "Excellent laptop for gaming and work",
                "pros": ["Great performance", "Good battery life", "Solid build"],
                "cons": ["Expensive", "Heavy"],
                "summary": "Overall excellent choice for power users",
                "verdict_score": 8.5
            }
        }
        score = self.scorer._score_extractability(rich_review_data)
        assert score >= 0.85, f"Rich review data should get high score, got {score}"
        
        print("✓ Extractability scoring works correctly")
    
    def test_content_quality_scoring(self):
        """Test content quality scoring based on completeness and consistency"""
        
        # High-quality e-commerce content
        quality_ecom_data = {
            "url": "https://example.com/laptop",
            "domain": "example.com",
            "page_type": "ecom",
            "product": {
                "title": "Dell XPS 15 Gaming Laptop - High Performance Computing",
                "brand": "Dell",
                "category": "electronics",
                "description": "Powerful gaming laptop with latest Intel processor, dedicated graphics, and premium build quality perfect for gaming and professional work",
                "features": ["Intel i7 processor", "NVIDIA RTX graphics", "16GB RAM", "1TB SSD", "4K display"]
            },
            "offer": {
                "price": 1599.99,
                "rating": 4.7
            }
        }
        score = self.scorer._score_content_quality(quality_ecom_data)
        assert score >= 0.79, f"High-quality e-commerce content should get high score, got {score}"
        
        # High-quality review content
        quality_review_data = {
            "url": "https://example.com/review",
            "domain": "example.com", 
            "page_type": "review",
            "review": {
                "headline": "Comprehensive review of the Dell XPS 15 laptop",
                "summary": "After extensive testing, this laptop delivers excellent performance for both gaming and professional work, though it comes at a premium price point",
                "pros": ["Excellent performance", "Great build quality", "Good battery life"],
                "cons": ["Expensive", "Can get hot under load"],
                "verdict_score": 8.2
            }
        }
        score = self.scorer._score_content_quality(quality_review_data)
        assert score >= 0.79, f"High-quality review content should get high score, got {score}"
        
        # Poor quality content
        poor_data = {
            "page_type": "ecom",
            "product": {
                "title": "Item"
            }
        }
        score = self.scorer._score_content_quality(poor_data)
        assert score <= 0.30, f"Poor quality content should get low score, got {score}"
        
        print("✓ Content quality scoring works correctly")
    
    def test_overall_credibility_scoring(self):
        """Test overall credibility scoring integration"""
        
        # High credibility source (trusted domain + recent + quality content)
        high_cred_data = {
            "url": "https://www.amazon.com/product/laptop-123",
            "domain": "www.amazon.com",
            "page_type": "ecom", 
            "product": {
                "title": "MacBook Air M2 - Latest Model",
                "brand": "Apple",
                "category": "electronics",
                "specs": {
                    "specifications": {
                        "cpu": "Apple M2",
                        "ram_gb": 16,
                        "storage_gb": 512
                    }
                }
            },
            "offer": {
                "price": 1199.99,
                "availability": "in_stock",
                "rating": 4.8
            },
            "review": {
                "published_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat() + "Z"
            }
        }
        
        score_result = self.scorer.score_source(
            "https://www.amazon.com/product/laptop-123",
            high_cred_data
        )
        
        assert score_result["overall_score"] >= 0.80, f"High credibility source should score >= 0.80, got {score_result['overall_score']}"
        assert score_result["credibility_tier"] == "high", f"Should be high tier, got {score_result['credibility_tier']}"
        
        # Low credibility source (unknown domain + old + poor content)
        low_cred_data = {
            "url": "https://unknown-site.com/item",
            "domain": "unknown-site.com",
            "page_type": "ecom",
            "product": {
                "title": "Item"
            },
            "review": {
                "published_at": (datetime.now(timezone.utc) - timedelta(days=900)).isoformat() + "Z"
            }
        }
        
        score_result = self.scorer.score_source(
            "https://unknown-site.com/item",
            low_cred_data
        )
        
        assert score_result["overall_score"] <= 0.50, f"Low credibility source should score <= 0.50, got {score_result['overall_score']}"
        assert score_result["credibility_tier"] in ["low", "very_low"], f"Should be low/very_low tier, got {score_result['credibility_tier']}"
        
        print("✓ Overall credibility scoring works correctly")
    
    def test_batch_scoring(self):
        """Test batch scoring and sorting functionality"""
        
        sources = [
            {
                "url": "https://unknown-site.com/product",
                "extracted_data": {"page_type": "ecom", "product": {"title": "Basic Item"}},
                "metadata": {}
            },
            {
                "url": "https://www.amazon.com/laptop",
                "extracted_data": {
                    "page_type": "ecom",
                    "product": {
                        "title": "Premium Laptop",
                        "brand": "Apple", 
                        "specs": {"specifications": {"cpu": "M2", "ram_gb": 16}}
                    },
                    "offer": {"price": 1299, "rating": 4.8}
                },
                "metadata": {}
            },
            {
                "url": "https://www.wirecutter.com/review",
                "extracted_data": {
                    "page_type": "review",
                    "review": {
                        "headline": "Best laptop review",
                        "summary": "Comprehensive analysis of top laptops",
                        "pros": ["Great performance"],
                        "cons": ["Expensive"],
                        "verdict_score": 9.0
                    }
                },
                "metadata": {}
            }
        ]
        
        scored_sources = self.scorer.batch_score_sources(sources)
        
        # Should return same number of sources
        assert len(scored_sources) == 3, f"Should return 3 sources, got {len(scored_sources)}"
        
        # Should be sorted by score (highest first)
        scores = [source["credibility_score"]["overall_score"] for source in scored_sources]
        assert scores == sorted(scores, reverse=True), f"Sources should be sorted by score: {scores}"
        
        # Amazon or Wirecutter should be first (both tier 1)
        top_domain = scored_sources[0]["credibility_score"]["url"]
        assert any(domain in top_domain for domain in ["amazon.com", "wirecutter.com"]), \
            f"Top source should be tier 1 domain, got {top_domain}"
        
        # Unknown site should be last
        bottom_domain = scored_sources[-1]["credibility_score"]["url"]
        assert "unknown-site.com" in bottom_domain, f"Bottom source should be unknown domain, got {bottom_domain}"
        
        print("✓ Batch scoring and sorting works correctly")
    
    def test_credibility_tiers(self):
        """Test credibility tier determination"""
        
        assert self.scorer._determine_credibility_tier(0.85) == "high"
        assert self.scorer._determine_credibility_tier(0.70) == "medium"
        assert self.scorer._determine_credibility_tier(0.50) == "low"
        assert self.scorer._determine_credibility_tier(0.30) == "very_low"
        
        print("✓ Credibility tier determination works correctly")
    
    def test_scoring_summary(self):
        """Test scoring methodology summary"""
        
        summary = self.scorer.get_scoring_summary()
        
        assert "methodology" in summary
        assert "components" in summary
        assert "tiers" in summary
        assert len(summary["components"]) == 4  # 4 scoring components
        assert len(summary["tiers"]) == 4  # 4 credibility tiers
        
        # Check component weights sum to 1.0
        total_weight = sum(
            component["weight"] 
            for component in summary["components"].values()
        )
        assert abs(total_weight - 1.0) < 0.01, f"Component weights should sum to 1.0, got {total_weight}"
        
        print("✓ Scoring summary works correctly")

if __name__ == "__main__":
    # Run tests manually if needed
    import sys
    
    test_instance = TestCredibilityScorer()
    test_instance.setup_class()
    
    try:
        test_instance.test_domain_reputation_scoring()
        test_instance.test_recency_scoring()
        test_instance.test_extractability_scoring() 
        test_instance.test_content_quality_scoring()
        test_instance.test_overall_credibility_scoring()
        test_instance.test_batch_scoring()
        test_instance.test_credibility_tiers()
        test_instance.test_scoring_summary()
        
        print("\n🎉 All credibility scorer tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)