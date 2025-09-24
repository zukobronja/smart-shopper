"""
Credibility scoring system for sources and extracted data
Evaluates domain reputation, recency, extractability, and content quality
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class CredibilityScorer:
    """
    Credibility scoring system implementing the strategy from TAVILY_EXPLORATION.md
    
    Scoring Components:
    1. Domain Reputation (0.40 weight) - Known trusted domains vs unknown
    2. Recency (0.25 weight) - How recent is the content
    3. Extractability (0.20 weight) - How well structured is the data
    4. Content Quality (0.15 weight) - Completeness and consistency
    """
    
    def __init__(self):
        self.weights = {
            "domain_reputation": 0.40,
            "recency": 0.25, 
            "extractability": 0.20,
            "content_quality": 0.15
        }
        
        # Domain reputation tiers (based on e-commerce and review site authority)
        self.domain_tiers = {
            "tier_1": {  # Highest trust - major retailers and review sites
                "domains": [
                    "amazon.com", "www.amazon.com",
                    "bestbuy.com", "www.bestbuy.com", 
                    "target.com", "www.target.com",
                    "walmart.com", "www.walmart.com",
                    "costco.com", "www.costco.com",
                    "homedepot.com", "www.homedepot.com",
                    "lowes.com", "www.lowes.com",
                    "wayfair.com", "www.wayfair.com",
                    "wirecutter.com", "www.wirecutter.com",
                    "techradar.com", "www.techradar.com", 
                    "cnet.com", "www.cnet.com",
                    "pcmag.com", "www.pcmag.com",
                    "consumerreports.org", "www.consumerreports.org"
                ],
                "score": 1.0
            },
            "tier_2": {  # Good trust - specialized retailers and niche review sites
                "domains": [
                    "newegg.com", "www.newegg.com",
                    "bhphotovideo.com", "www.bhphotovideo.com",
                    "williams-sonoma.com", "www.williams-sonoma.com",
                    "ikea.com", "www.ikea.com",
                    "wayfair.com", "www.wayfair.com",
                    "overstock.com", "www.overstock.com",
                    "engadget.com", "www.engadget.com",
                    "tomsguide.com", "www.tomsguide.com",
                    "digitaltrends.com", "www.digitaltrends.com"
                ],
                "score": 0.80
            },
            "tier_3": {  # Moderate trust - other known e-commerce sites
                "domains": [
                    "ebay.com", "www.ebay.com",
                    "etsy.com", "www.etsy.com", 
                    "shopify.com",
                    "woocommerce.com",
                    "squarespace.com"
                ],
                "score": 0.60
            }
        }
        
        # Default scores for unknown domains
        self.unknown_domain_score = 0.30
        
    def score_source(
        self, 
        url: str, 
        extracted_data: Optional[Dict[str, Any]] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compute comprehensive credibility score for a source
        
        Args:
            url: Source URL
            extracted_data: Extracted structured data (if available)
            extraction_metadata: Metadata about extraction process
            
        Returns:
            Dict with overall score and component breakdowns
        """
        try:
            logger.info(f"Computing credibility score for {url}")
            
            # Component scores
            domain_score = self._score_domain_reputation(url)
            recency_score = self._score_recency(extracted_data, extraction_metadata)
            extractability_score = self._score_extractability(extracted_data, extraction_metadata)
            content_quality_score = self._score_content_quality(extracted_data)
            
            # Weighted overall score
            overall_score = (
                domain_score * self.weights["domain_reputation"] +
                recency_score * self.weights["recency"] +
                extractability_score * self.weights["extractability"] + 
                content_quality_score * self.weights["content_quality"]
            )
            
            # Determine credibility tier
            tier = self._determine_credibility_tier(overall_score)
            
            score_breakdown = {
                "overall_score": round(overall_score, 3),
                "credibility_tier": tier,
                "component_scores": {
                    "domain_reputation": round(domain_score, 3),
                    "recency": round(recency_score, 3),
                    "extractability": round(extractability_score, 3),
                    "content_quality": round(content_quality_score, 3)
                },
                "weights": self.weights,
                "url": url,
                "scored_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Credibility score: {overall_score:.3f} ({tier})")
            return score_breakdown
            
        except Exception as e:
            logger.error(f"Failed to score credibility for {url}: {e}")
            return self._fallback_score(url)
    
    def _score_domain_reputation(self, url: str) -> float:
        """Score based on domain reputation and trustworthiness"""
        try:
            domain = self._extract_domain(url)
            
            # Check each tier
            for tier_name, tier_data in self.domain_tiers.items():
                if domain in tier_data["domains"]:
                    logger.debug(f"Domain {domain} found in {tier_name}")
                    return tier_data["score"]
            
            # Unknown domain - check for common e-commerce indicators
            if self._has_ecommerce_indicators(url):
                return self.unknown_domain_score + 0.20  # Boost for e-commerce structure
            
            return self.unknown_domain_score
            
        except Exception as e:
            logger.warning(f"Domain reputation scoring failed: {e}")
            return self.unknown_domain_score
    
    def _score_recency(
        self, 
        extracted_data: Optional[Dict[str, Any]] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score based on content recency and freshness"""
        try:
            now = datetime.now(timezone.utc)
            
            # Try to find publication/update date in extracted data
            pub_date = None
            if extracted_data:
                # Check review data
                review = extracted_data.get("review", {})
                pub_date_str = review.get("published_at") or review.get("updated_at")
                
                if pub_date_str:
                    try:
                        # Handle Z suffix for UTC (remove +00:00Z format)
                        if pub_date_str.endswith('+00:00Z'):
                            pub_date_str = pub_date_str[:-1]  # Remove just the Z
                        elif pub_date_str.endswith('Z'):
                            pub_date_str = pub_date_str[:-1] + '+00:00'
                        pub_date = datetime.fromisoformat(pub_date_str)
                        # Ensure timezone aware
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                    except:
                        pass
            
            # If no explicit date found, use extraction metadata or assume moderate age
            if not pub_date and extraction_metadata:
                extracted_at = extraction_metadata.get("extracted_at")
                if extracted_at:
                    try:
                        if extracted_at.endswith('Z'):
                            extracted_at = extracted_at[:-1] + '+00:00'
                        pub_date = datetime.fromisoformat(extracted_at)
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        # Assume content is slightly older than extraction
                        pub_date = pub_date - timedelta(days=30)
                    except:
                        pass
            
            if not pub_date:
                # No date info - assume moderate age (6 months)
                return 0.60
                
            # Calculate age in days
            age_days = (now - pub_date).days
            
            if age_days < 0:
                # Future date (probably error) - moderate score
                return 0.60
            elif age_days <= 7:
                # Very fresh (within a week)
                return 1.0
            elif age_days <= 30:
                # Fresh (within a month)
                return 0.90
            elif age_days <= 90: 
                # Recent (within 3 months)
                return 0.75
            elif age_days <= 180:
                # Moderately recent (within 6 months)
                return 0.60
            elif age_days <= 365:
                # Somewhat old (within a year)
                return 0.45
            elif age_days <= 730:
                # Old (within 2 years)
                return 0.30
            else:
                # Very old (over 2 years)
                return 0.15
                
        except Exception as e:
            logger.warning(f"Recency scoring failed: {e}")
            return 0.60  # Default moderate score
    
    def _score_extractability(
        self,
        extracted_data: Optional[Dict[str, Any]] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score based on how well-structured and extractable the content is"""
        try:
            if not extracted_data:
                return 0.30  # Low score if no data extracted
            
            # Check if extraction was successful and well-structured
            score = 0.0
            
            # Base score for having any structured data
            score += 0.40
            
            # E-commerce data quality indicators
            if extracted_data.get("page_type") == "ecom":
                product = extracted_data.get("product", {})
                offer = extracted_data.get("offer", {})
                
                # Product data completeness
                if product.get("title"):
                    score += 0.10
                if product.get("brand"):
                    score += 0.05
                if product.get("category"):
                    score += 0.05
                    
                # Specifications richness
                specs = product.get("specs", {})
                if specs and isinstance(specs, dict):
                    spec_count = len(specs.get("specifications", {}))
                    score += min(0.15, spec_count * 0.02)  # Up to 0.15 for rich specs
                
                # Offer data completeness
                if offer.get("price"):
                    score += 0.10
                if offer.get("availability"):
                    score += 0.05
                if offer.get("rating"):
                    score += 0.05
                    
            # Review data quality indicators
            elif extracted_data.get("page_type") == "review":
                review = extracted_data.get("review", {})
                
                if review.get("headline"):
                    score += 0.10
                if review.get("pros") and isinstance(review.get("pros"), list):
                    score += 0.10
                if review.get("cons") and isinstance(review.get("cons"), list):
                    score += 0.10
                if review.get("summary"):
                    score += 0.15
                if review.get("verdict_score"):
                    score += 0.10
            
            # Check extraction metadata for additional quality indicators
            if extraction_metadata:
                coverage = extraction_metadata.get("coverage")
                if coverage and coverage >= 0.70:
                    score += 0.05  # Bonus for high coverage
                    
            return min(1.0, score)
            
        except Exception as e:
            logger.warning(f"Extractability scoring failed: {e}")
            return 0.50
    
    def _score_content_quality(self, extracted_data: Optional[Dict[str, Any]] = None) -> float:
        """Score based on content completeness, consistency, and quality"""
        try:
            if not extracted_data:
                return 0.30
            
            score = 0.0
            
            # General quality indicators
            if extracted_data.get("url") and extracted_data.get("domain"):
                score += 0.10
                
            if extracted_data.get("page_type") == "ecom":
                product = extracted_data.get("product", {})
                offer = extracted_data.get("offer", {})
                
                # Content richness
                title = product.get("title", "")
                if len(title) > 10:  # Reasonable title length
                    score += 0.15
                    
                description = product.get("description", "")
                if len(description) > 50:  # Detailed description
                    score += 0.10
                    
                features = product.get("features", [])
                if features and len(features) >= 3:  # Multiple features listed
                    score += 0.10
                
                # Price consistency
                price = offer.get("price")
                if price and isinstance(price, (int, float)) and price > 0:
                    score += 0.15
                    
                # Brand/category consistency
                brand = product.get("brand", "")
                category = product.get("category", "")
                if brand and category:
                    score += 0.10
                    
                # Rating reasonableness
                rating = offer.get("rating")
                if rating and isinstance(rating, (int, float)) and 0 <= rating <= 5:
                    score += 0.10
                    
            elif extracted_data.get("page_type") == "review":
                review = extracted_data.get("review", {})
                
                headline = review.get("headline", "")
                if len(headline) > 10:
                    score += 0.15
                    
                summary = review.get("summary", "")
                if len(summary) > 50:
                    score += 0.20
                    
                pros = review.get("pros", [])
                cons = review.get("cons", [])
                if pros and cons:  # Balanced review
                    score += 0.20
                    
                verdict_score = review.get("verdict_score")
                if verdict_score and isinstance(verdict_score, (int, float)) and 0 <= verdict_score <= 10:
                    score += 0.15
                    
            return min(1.0, score)
            
        except Exception as e:
            logger.warning(f"Content quality scoring failed: {e}")
            return 0.50
    
    def _determine_credibility_tier(self, score: float) -> str:
        """Determine credibility tier based on overall score"""
        if score >= 0.80:
            return "high"
        elif score >= 0.60:
            return "medium"
        elif score >= 0.40:
            return "low"
        else:
            return "very_low"
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return ""
    
    def _has_ecommerce_indicators(self, url: str) -> bool:
        """Check if URL has common e-commerce indicators"""
        url_lower = url.lower()
        indicators = [
            "/product/", "/item/", "/p/", "/dp/", 
            "shop", "store", "buy", "cart", "checkout",
            "price", "sale", "deal"
        ]
        return any(indicator in url_lower for indicator in indicators)
    
    def _fallback_score(self, url: str) -> Dict[str, Any]:
        """Return fallback score when scoring fails"""
        return {
            "overall_score": 0.40,
            "credibility_tier": "low", 
            "component_scores": {
                "domain_reputation": 0.30,
                "recency": 0.50,
                "extractability": 0.40,
                "content_quality": 0.40
            },
            "weights": self.weights,
            "url": url,
            "scored_at": datetime.now(timezone.utc).isoformat(),
            "error": "Scoring failed, using fallback"
        }
    
    def batch_score_sources(
        self, 
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Score multiple sources and return sorted by credibility
        
        Args:
            sources: List of source dicts with url, extracted_data, metadata
            
        Returns:
            List of sources with credibility scores, sorted by score desc
        """
        try:
            logger.info(f"Batch scoring {len(sources)} sources")
            
            scored_sources = []
            for source in sources:
                url = source.get("url", "")
                extracted_data = source.get("extracted_data")
                metadata = source.get("metadata")
                
                credibility_score = self.score_source(url, extracted_data, metadata)
                
                source_with_score = source.copy()
                source_with_score["credibility_score"] = credibility_score
                scored_sources.append(source_with_score)
            
            # Sort by overall score descending
            scored_sources.sort(
                key=lambda x: x["credibility_score"]["overall_score"], 
                reverse=True
            )
            
            logger.info(f"Batch scoring complete, top score: {scored_sources[0]['credibility_score']['overall_score']:.3f}")
            return scored_sources
            
        except Exception as e:
            logger.error(f"Batch scoring failed: {e}")
            return sources  # Return original sources if scoring fails
    
    def get_scoring_summary(self) -> Dict[str, Any]:
        """Get summary of scoring methodology and parameters"""
        return {
            "methodology": "Weighted credibility scoring",
            "components": {
                "domain_reputation": {
                    "weight": self.weights["domain_reputation"],
                    "description": "Domain trustworthiness and authority"
                },
                "recency": {
                    "weight": self.weights["recency"], 
                    "description": "Content freshness and publication date"
                },
                "extractability": {
                    "weight": self.weights["extractability"],
                    "description": "Data structure quality and completeness"
                },
                "content_quality": {
                    "weight": self.weights["content_quality"],
                    "description": "Content richness and consistency"
                }
            },
            "tiers": {
                "high": "≥ 0.80 - Highly credible sources",
                "medium": "≥ 0.60 - Moderately credible sources", 
                "low": "≥ 0.40 - Questionable credibility",
                "very_low": "< 0.40 - Low credibility sources"
            },
            "domain_tiers": len(self.domain_tiers)
        }