"""
ResultsRankerAgent for SmartShopper Pipeline

Intelligent multi-criteria ranking system that scores and ranks structured products
based on relevance, value, quality, and user preferences. Features:

- Semantic relevance scoring using embeddings
- Competitive price/value analysis within categories  
- Source quality integration from credibility scores
- Intent-aware weighting (product_search vs comparison vs review_search)
- Category-specific optimization (electronics vs kitchen vs fashion)
- Hybrid explanation system (templates + LLM enhancement)

Architecture Position: SpecExtractor → ResultsRanker → Final Output
Input: state["structured_products"] 
Output: state["ranked_products"]
"""
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from statistics import mean
from collections import defaultdict

from app.agents.state import SmartShopperAgent, SmartShopperWorkflowState, add_agent_step
from app.config import settings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from sentence_transformers import SentenceTransformer


class SemanticRelevanceScorer:
    """Calculates semantic relevance between user query and products"""
    
    def __init__(self):
        self.openai_embeddings = None
        self.sentence_model = None
        self._init_models()
    
    def _init_models(self):
        """Initialize embedding models based on settings"""
        try:
            if settings.EMBEDDINGS_PROVIDER == "openai":
                self.openai_embeddings = OpenAIEmbeddings(
                    api_key=settings.OPENAI_API_KEY,
                    model="text-embedding-3-small"
                )
            else:
                # Default to MiniLM for fast local embeddings
                self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print(f"Warning: Could not initialize embeddings: {e}")
            # Fallback to simple text matching
    
    async def calculate_relevance(self, query_text: str, product: Dict[str, Any]) -> float:
        """
        Calculate semantic relevance between query and product
        
        Args:
            query_text: User's search query
            product: Product dictionary with title, specs, etc.
            
        Returns:
            float: Relevance score 0.0-1.0
        """
        try:
            # Create searchable product text
            product_text = self._create_product_text(product)
            
            # Try embedding-based similarity first
            if settings.EMBEDDINGS_PROVIDER == "openai" and self.openai_embeddings:
                return await self._calculate_embedding_similarity_openai(query_text, product_text)
            elif self.sentence_model:
                return self._calculate_embedding_similarity_local(query_text, product_text)
            else:
                # Fallback to keyword matching
                return self._calculate_keyword_similarity(query_text, product_text)
        except Exception as e:
            print(f"Error calculating relevance: {e}")
            # Fallback to keyword matching
            return self._calculate_keyword_similarity(query_text, product_text)
    
    def _create_product_text(self, product: Dict[str, Any]) -> str:
        """Create searchable text from product data"""
        text_parts = []
        
        # Title (highest weight)
        if product.get("title"):
            text_parts.append(product["title"])
        
        # Brand and category
        if product.get("brand"):
            text_parts.append(product["brand"])
        if product.get("category"):
            text_parts.append(product["category"])
        
        # Specifications (important for technical queries)
        specs = product.get("specs", {})
        for key, value in specs.items():
            if value:
                text_parts.append(f"{key} {value}")
        
        return " ".join(text_parts)
    
    async def _calculate_embedding_similarity_openai(self, query: str, product_text: str) -> float:
        """Calculate similarity using OpenAI embeddings"""
        try:
            # Get embeddings
            query_embedding = await self.openai_embeddings.aembed_query(query)
            product_embedding = await self.openai_embeddings.aembed_query(product_text)
            
            # Calculate cosine similarity
            return self._cosine_similarity(query_embedding, product_embedding)
        except Exception as e:
            print(f"OpenAI embedding error: {e}")
            return self._calculate_keyword_similarity(query, product_text)
    
    def _calculate_embedding_similarity_local(self, query: str, product_text: str) -> float:
        """Calculate similarity using local SentenceTransformer"""
        try:
            # Get embeddings
            embeddings = self.sentence_model.encode([query, product_text])
            query_embedding, product_embedding = embeddings[0], embeddings[1]
            
            # Calculate cosine similarity
            return self._cosine_similarity(query_embedding.tolist(), product_embedding.tolist())
        except Exception as e:
            print(f"Local embedding error: {e}")
            return self._calculate_keyword_similarity(query, product_text)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            import numpy as np
            
            vec1_np = np.array(vec1)
            vec2_np = np.array(vec2)
            
            # Cosine similarity
            dot_product = np.dot(vec1_np, vec2_np)
            norm1 = np.linalg.norm(vec1_np)
            norm2 = np.linalg.norm(vec2_np)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            # Convert to 0-1 range (cosine similarity is -1 to 1)
            return max(0.0, (similarity + 1) / 2)
        except Exception:
            return 0.0
    
    def _calculate_keyword_similarity(self, query: str, product_text: str) -> float:
        """Fallback keyword-based similarity"""
        query_words = set(query.lower().split())
        product_words = set(product_text.lower().split())
        
        if not query_words or not product_words:
            return 0.0
        
        # Jaccard similarity with boost for exact matches
        intersection = len(query_words & product_words)
        union = len(query_words | product_words)
        
        base_score = intersection / union if union > 0 else 0.0
        
        # Boost for title matches (more important)
        title = product_text.split()[0] if product_text else ""
        title_boost = 0.2 if any(word in title.lower() for word in query_words) else 0.0
        
        return min(1.0, base_score + title_boost)


class PriceValueScorer:
    """Calculates price competitiveness and value within category"""
    
    def calculate_value_score(self, product: Dict[str, Any], category_products: List[Dict[str, Any]]) -> float:
        """
        Calculate price value score within category context
        
        Args:
            product: Target product
            category_products: All products in same category for comparison
            
        Returns:
            float: Value score 0.0-1.0 (higher = better value)
        """
        try:
            product_price = self._extract_price(product)
            if product_price is None:
                return 0.5  # Neutral score for missing price
            
            # Get comparable products (same category)
            comparable_prices = []
            for p in category_products:
                price = self._extract_price(p)
                if price is not None and price > 0:
                    comparable_prices.append(price)
            
            if len(comparable_prices) < 2:
                return 0.5  # Can't compare, neutral score
            
            # Calculate percentile ranking (lower price = higher score)
            prices_sorted = sorted(comparable_prices)
            product_percentile = self._get_percentile_rank(product_price, prices_sorted)
            
            # Invert percentile so lower price = higher score
            base_score = 1.0 - product_percentile
            
            # Apply feature-adjusted scoring
            feature_adjustment = self._calculate_feature_adjustment(product, category_products)
            
            # Detect deals (was_price vs current price)
            deal_boost = self._calculate_deal_boost(product)
            
            final_score = min(1.0, base_score + feature_adjustment + deal_boost)
            return max(0.0, final_score)
            
        except Exception as e:
            print(f"Error calculating value score: {e}")
            return 0.5
    
    def _extract_price(self, product: Dict[str, Any]) -> Optional[float]:
        """Extract price from product data"""
        # Try direct price field
        if product.get("price"):
            return float(product["price"])
        
        # Try specs for price
        specs = product.get("specs", {})
        for key, value in specs.items():
            if "price" in key.lower() and value:
                # Extract numeric value from price string
                price_match = re.search(r'[\d,]+\.?\d*', str(value).replace(',', ''))
                if price_match:
                    return float(price_match.group())
        
        return None
    
    def _get_percentile_rank(self, value: float, sorted_values: List[float]) -> float:
        """Get percentile rank of value in sorted list"""
        if not sorted_values:
            return 0.5
        
        count_below = sum(1 for v in sorted_values if v < value)
        count_equal = sum(1 for v in sorted_values if v == value)
        
        # Standard percentile rank formula
        rank = (count_below + 0.5 * count_equal) / len(sorted_values)
        return max(0.0, min(1.0, rank))
    
    def _calculate_feature_adjustment(self, product: Dict[str, Any], category_products: List[Dict[str, Any]]) -> float:
        """Adjust score based on feature richness vs price"""
        try:
            # Simple feature count adjustment
            product_features = len(product.get("specs", {}))
            if product_features == 0:
                return 0.0
            
            # Compare feature richness to category average
            category_features = [len(p.get("specs", {})) for p in category_products]
            avg_features = mean(category_features) if category_features else 1
            
            # Boost score if product has more features than average
            if avg_features > 0:
                feature_ratio = product_features / avg_features
                if feature_ratio > 1.2:  # 20% more features
                    return 0.1
                elif feature_ratio > 1.1:  # 10% more features
                    return 0.05
            
            return 0.0
        except Exception:
            return 0.0
    
    def _calculate_deal_boost(self, product: Dict[str, Any]) -> float:
        """Calculate boost for deals/discounts"""
        try:
            current_price = self._extract_price(product)
            if current_price is None:
                return 0.0
            
            # Look for was_price or original price
            was_price = None
            specs = product.get("specs", {})
            
            for key, value in specs.items():
                if "was" in key.lower() or "original" in key.lower() or "msrp" in key.lower():
                    price_match = re.search(r'[\d,]+\.?\d*', str(value).replace(',', ''))
                    if price_match:
                        was_price = float(price_match.group())
                        break
            
            if was_price and was_price > current_price:
                discount_percent = (was_price - current_price) / was_price
                # Boost proportional to discount (max 0.2 for 50%+ discount)
                return min(0.2, discount_percent * 0.4)
            
            return 0.0
        except Exception:
            return 0.0


class QualityAssessmentScorer:
    """Assesses product quality using credibility and completeness metrics"""
    
    def assess_quality(self, product: Dict[str, Any]) -> float:
        """
        Assess overall product quality score
        
        Args:
            product: Product data with credibility_score and specs
            
        Returns:
            float: Quality score 0.0-1.0
        """
        try:
            # Source credibility (from CredibilityFilterAgent)
            credibility_score = product.get("credibility_score", 0.7)
            
            # Specification completeness
            completeness_score = self._calculate_completeness_score(product)
            
            # Product maturity indicators
            maturity_score = self._calculate_maturity_score(product)
            
            # Weighted combination
            quality_score = (
                0.6 * credibility_score +
                0.3 * completeness_score +
                0.1 * maturity_score
            )
            
            return max(0.0, min(1.0, quality_score))
            
        except Exception as e:
            print(f"Error calculating quality score: {e}")
            return 0.7  # Default neutral score
    
    def _calculate_completeness_score(self, product: Dict[str, Any]) -> float:
        """Calculate score based on data completeness"""
        try:
            score = 0.0
            
            # Required fields scoring
            if product.get("title"):
                score += 0.3
            if product.get("brand"):
                score += 0.2
            if product.get("price"):
                score += 0.2
            if product.get("category"):
                score += 0.1
            
            # Specifications richness
            specs = product.get("specs", {})
            spec_count = len([v for v in specs.values() if v])
            
            if spec_count >= 10:
                score += 0.2
            elif spec_count >= 5:
                score += 0.15
            elif spec_count >= 3:
                score += 0.1
            elif spec_count >= 1:
                score += 0.05
            
            return min(1.0, score)
            
        except Exception:
            return 0.5
    
    def _calculate_maturity_score(self, product: Dict[str, Any]) -> float:
        """Calculate maturity score based on product indicators"""
        try:
            score = 0.5  # Base score
            
            # Look for indicators in specs
            specs = product.get("specs", {})
            
            # Positive indicators
            for key, value in specs.items():
                key_lower = key.lower()
                value_str = str(value).lower() if value else ""
                
                # Awards, certifications
                if any(word in key_lower for word in ["award", "certified", "rating"]):
                    score += 0.1
                    break
                
                # Version/generation indicators (suggests established product)
                if any(word in value_str for word in ["gen", "version", "v2", "v3", "pro", "plus"]):
                    score += 0.05
                    break
            
            return min(1.0, max(0.0, score))
            
        except Exception:
            return 0.5


class RankingExplainer:
    """Generates explanations for why products rank as they do"""
    
    def __init__(self):
        self.llm = None
        self._init_llm()
    
    def _init_llm(self):
        """Initialize LLM for explanation enhancement"""
        try:
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                api_key=settings.OPENAI_API_KEY
            )
        except Exception as e:
            print(f"Warning: Could not initialize LLM for explanations: {e}")
    
    async def generate_explanation(
        self,
        product: Dict[str, Any],
        scores: Dict[str, float],
        rank: int,
        query: str,
        category_context: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate ranking explanation using hybrid approach
        
        Args:
            product: Product data
            scores: Score breakdown dict
            rank: Product rank (1-indexed)
            query: User query
            category_context: Other products for comparison
            
        Returns:
            str: Human-readable explanation
        """
        try:
            # Start with template-based explanation
            template_explanation = self._generate_template_explanation(product, scores, rank, query)
            
            # Enhance with LLM if available and appropriate
            if self.llm and rank <= 3:  # Only enhance top 3 for cost efficiency
                enhanced_explanation = await self._enhance_with_llm(
                    template_explanation, product, scores, query, category_context
                )
                return enhanced_explanation
            
            return template_explanation
            
        except Exception as e:
            print(f"Error generating explanation: {e}")
            return self._generate_simple_explanation(product, rank)
    
    def _generate_template_explanation(
        self,
        product: Dict[str, Any],
        scores: Dict[str, float],
        rank: int,
        query: str
    ) -> str:
        """Generate explanation using templates"""
        try:
            title = product.get("title", "Unknown Product")
            price = product.get("price")
            brand = product.get("brand")
            
            # Determine primary ranking factor
            score_items = [(k, v) for k, v in scores.items() if k != "final_score"]
            top_score = max(score_items, key=lambda x: x[1]) if score_items else ("relevance", 0.5)
            
            # Build explanation based on top score
            if rank == 1:
                explanation = f"RANKING: **Top Choice**: {title}"
            elif rank <= 3:
                explanation = f"FILTERING: **#{rank} Ranked**: {title}"
            else:
                explanation = f"#{rank}: {title}"
            
            # Add primary strength
            if top_score[0] == "relevance" and top_score[1] > 0.7:
                explanation += " - Perfect match for your search"
            elif top_score[0] == "value" and top_score[1] > 0.8:
                explanation += " - Excellent value for money"
            elif top_score[0] == "quality" and top_score[1] > 0.8:
                explanation += " - High-quality from trusted source"
            
            # Add price context if available
            if price:
                explanation += f" at ${price:,.2f}"
            
            # Add brand context
            if brand:
                explanation += f" by {brand}"
            
            return explanation
            
        except Exception as e:
            print(f"Error in template explanation: {e}")
            return f"#{rank}: {product.get('title', 'Product')}"
    
    async def _enhance_with_llm(
        self,
        template_explanation: str,
        product: Dict[str, Any],
        scores: Dict[str, float],
        query: str,
        category_context: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Enhance explanation using LLM"""
        try:
            # Prepare context for LLM
            product_summary = {
                "title": product.get("title", ""),
                "brand": product.get("brand", ""),
                "price": product.get("price"),
                "category": product.get("category", ""),
                "key_specs": {k: v for k, v in product.get("specs", {}).items() if k in ["processor", "memory", "storage", "capacity", "power", "size"]}
            }
            
            prompt = f"""
            Enhance this product ranking explanation to be more helpful and specific:
            
            Current explanation: "{template_explanation}"
            
            User query: "{query}"
            Product: {json.dumps(product_summary, indent=2)}
            Scores: {json.dumps(scores, indent=2)}
            
            Please provide a concise, helpful explanation (max 2 sentences) that highlights:
            1. Why this product matches the user's query
            2. Its key competitive advantage or value proposition
            
            Be specific about features when relevant but keep it conversational.
            """
            
            response = await self.llm.ainvoke(prompt)
            enhanced = response.content.strip()
            
            # Fallback to template if LLM response is too long or unhelpful
            if len(enhanced) > 200 or not enhanced:
                return template_explanation
            
            return enhanced
            
        except Exception as e:
            print(f"Error enhancing with LLM: {e}")
            return template_explanation
    
    def _generate_simple_explanation(self, product: Dict[str, Any], rank: int) -> str:
        """Simple fallback explanation"""
        title = product.get("title", "Product")
        price = product.get("price")
        
        explanation = f"#{rank}: {title}"
        if price:
            explanation += f" - ${price:,.2f}"
        
        return explanation


class ResultsRankerAgent(SmartShopperAgent):
    """
    Intelligent multi-criteria product ranking agent
    
    Ranks structured products using:
    - Semantic relevance to user query
    - Price competitiveness within category  
    - Source quality and credibility
    - Intent-aware and category-specific weighting
    - Comprehensive explanations for transparency
    """
    
    name = "Results Ranker"
    color = SmartShopperAgent.GREEN
    
    def __init__(self):
        super().__init__()
        self.relevance_scorer = SemanticRelevanceScorer()
        self.value_scorer = PriceValueScorer()
        self.quality_scorer = QualityAssessmentScorer()
        self.explainer = RankingExplainer()
        self.log("Initialized ResultsRankerAgent")
    
    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """
        Main processing method - rank structured products
        
        Args:
            state: Current pipeline state
            
        Returns:
            SmartShopperWorkflowState: Updated state with ranked_products
        """
        start_time = datetime.now()
        self.log("RANKING: Starting intelligent product ranking")
        
        try:
            # Get input data
            structured_products = state.get("structured_products", [])
            search_query = state.get("search_query", {})
            query_text = search_query.normalized_query if search_query else state.get("raw_query", "")
            intent = search_query.intent if search_query else "product_search"
            
            if not structured_products:
                self.log("ERROR: No structured products to rank")
                state["ranked_products"] = []
                add_agent_step(
                    state, self.name, "skipped", 0,
                    error_message="No products to rank"
                )
                return state
            
            self.log(f"METRICS: Ranking {len(structured_products)} products for query: '{query_text}'")
            
            # Group products by category for competitive analysis
            products_by_category = self._group_by_category(structured_products)
            
            # Calculate scores for each product
            ranked_products = []
            
            for i, product in enumerate(structured_products):
                try:
                    self.log(f"PROCESSING: Processing product {i+1}/{len(structured_products)}: {product.get('title', 'Unknown')[:50]}")
                    
                    # Get category context
                    category = product.get("category", "general")
                    category_products = products_by_category.get(category, structured_products)
                    
                    # Calculate individual scores
                    scores = await self._calculate_product_scores(
                        product, query_text, intent, category_products
                    )
                    
                    # Create ranked product entry
                    ranked_product = {
                        **product,  # Include all original product data
                        "scores": scores,
                        "final_score": scores["final_score"],
                        "rank": 0,  # Will be set after sorting
                        "explanation": ""  # Will be generated after ranking
                    }
                    
                    ranked_products.append(ranked_product)
                    
                except Exception as e:
                    self.log(f"ERROR: Error processing product {i+1}: {e}")
                    # Include product with default scores
                    ranked_products.append({
                        **product,
                        "scores": {"relevance": 0.5, "value": 0.5, "quality": 0.5, "final_score": 0.5},
                        "final_score": 0.5,
                        "rank": 0,
                        "explanation": "Error in ranking calculation"
                    })
            
            # Sort by final score (descending)
            ranked_products.sort(key=lambda x: x["final_score"], reverse=True)
            
            # Assign ranks and generate explanations
            for i, product in enumerate(ranked_products):
                product["rank"] = i + 1
                try:
                    # Generate explanation for top products
                    if i < 10:  # Only explain top 10 for performance
                        product["explanation"] = await self.explainer.generate_explanation(
                            product, product["scores"], i + 1, query_text, ranked_products[:5]
                        )
                    else:
                        product["explanation"] = f"#{i+1}: {product.get('title', 'Product')}"
                except Exception as e:
                    self.log(f"WARNING: Error generating explanation for rank {i+1}: {e}")
                    product["explanation"] = f"#{i+1}: {product.get('title', 'Product')}"
            
            # Update state
            state["ranked_products"] = ranked_products
            
            # Log results summary
            total_products = len(ranked_products)
            avg_score = mean([p["final_score"] for p in ranked_products]) if ranked_products else 0
            top_product = ranked_products[0] if ranked_products else None
            
            self.log(f"SUCCESS: Ranked {total_products} products (avg score: {avg_score:.2f})")
            if top_product:
                self.log(f"TOP: Top result: {top_product.get('title', 'Unknown')[:50]} (score: {top_product['final_score']:.3f})")
            
            # Track execution
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            add_agent_step(
                state, self.name, "success", execution_time,
                items_processed=total_products,
                metadata={
                    "average_score": avg_score,
                    "top_score": top_product["final_score"] if top_product else 0,
                    "intent": intent,
                    "categories": list(products_by_category.keys())
                }
            )
            
            return state
            
        except Exception as e:
            self.log(f"ERROR: Fatal error in ranking: {e}")
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            add_agent_step(
                state, self.name, "error", execution_time,
                error_message=str(e)
            )
            # Return original state with empty ranking
            state["ranked_products"] = []
            return state
    
    def _group_by_category(self, products: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group products by category for competitive analysis"""
        groups = defaultdict(list)
        
        for product in products:
            category = product.get("category", "general")
            groups[category].append(product)
        
        return dict(groups)
    
    async def _calculate_product_scores(
        self,
        product: Dict[str, Any],
        query_text: str,
        intent: str,
        category_products: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate all scoring components for a product"""
        
        # Calculate individual scores
        relevance_score = await self.relevance_scorer.calculate_relevance(query_text, product)
        value_score = self.value_scorer.calculate_value_score(product, category_products)
        quality_score = self.quality_scorer.assess_quality(product)
        
        # Apply intent-aware weighting
        weights = self._get_intent_weights(intent, product.get("category", "general"))
        
        # Calculate final weighted score
        final_score = (
            weights["relevance"] * relevance_score +
            weights["value"] * value_score +
            weights["quality"] * quality_score
        )
        
        return {
            "relevance": relevance_score,
            "value": value_score,
            "quality": quality_score,
            "final_score": min(1.0, max(0.0, final_score))
        }
    
    def _get_intent_weights(self, intent: str, category: str) -> Dict[str, float]:
        """Get scoring weights based on search intent and category"""
        
        # Base weights from architecture docs
        base_weights = {
            "relevance": 0.4,
            "value": 0.3,
            "quality": 0.3
        }
        
        # Intent-specific adjustments
        if intent == "comparison":
            # For comparisons, emphasize quality and specifications
            return {
                "relevance": 0.35,
                "value": 0.25,
                "quality": 0.40
            }
        elif intent == "review_search":
            # For review searches, emphasize quality and credibility
            return {
                "relevance": 0.30,
                "value": 0.25,
                "quality": 0.45
            }
        elif intent == "product_search":
            # For product searches, check if budget-focused
            return {
                "relevance": 0.40,
                "value": 0.35,
                "quality": 0.25
            }
        
        # Category-specific fine-tuning
        if category in ["electronics", "laptop", "smartphone"]:
            # Technical products: relevance matters more
            base_weights["relevance"] += 0.05
            base_weights["value"] -= 0.025
            base_weights["quality"] -= 0.025
        elif category in ["kitchen", "appliance"]:
            # Appliances: quality and durability matter
            base_weights["quality"] += 0.05
            base_weights["relevance"] -= 0.025
            base_weights["value"] -= 0.025
        elif category in ["toys", "games"]:
            # Fun products: value matters more
            base_weights["value"] += 0.05
            base_weights["quality"] -= 0.025
            base_weights["relevance"] -= 0.025
        
        return base_weights


# Export the main agent class
__all__ = ["ResultsRankerAgent"]