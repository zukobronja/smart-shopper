"""
SpecExtractorAgent for SmartShopper Pipeline

Extracts structured product specifications from credibility-filtered content using
a universal, category-agnostic approach. Works with ANY product type:
- Electronics (laptops, phones, headphones)
- Kitchen appliances (blenders, toasters, cookware)  
- Clothing & fashion (shirts, shoes, accessories)
- Toys & games (LEGO, puzzles, action figures)
- Furniture (chairs, tables, storage)
- Automotive (tires, parts, accessories)
- Books, beauty products, and more

Architecture Position: CredibilityFilter → SpecExtractor → ResultsRanker
"""
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.agents.state import SmartShopperAgent, SmartShopperWorkflowState, add_agent_step
from app.config import settings
from langchain_openai import ChatOpenAI


class UniversalCategoryDetector:
    """Detects product category from title and content"""
    
    CATEGORY_KEYWORDS = {
        "laptop": ["laptop", "notebook", "macbook", "thinkpad", "gaming laptop", "ultrabook"],
        "smartphone": ["phone", "iphone", "galaxy", "pixel", "android", "mobile phone"],
        "tablet": ["tablet", "ipad", "android tablet", "kindle", "surface"],
        "headphones": ["headphones", "earbuds", "airpods", "earphones", "headset"],
        "monitor": ["monitor", "display", "screen", "gaming monitor", "4k monitor"],
        "keyboard": ["keyboard", "mechanical keyboard", "gaming keyboard"],
        "mouse": ["mouse", "gaming mouse", "wireless mouse"],
        "camera": ["camera", "dslr", "mirrorless", "point and shoot", "action camera"],
        "speaker": ["speaker", "bluetooth speaker", "smart speaker", "soundbar"],
        "tv": ["tv", "television", "smart tv", "4k tv", "oled"],
        
        # Kitchen & Home
        "kitchen": ["blender", "toaster", "microwave", "coffee maker", "cookware", "pot", "pan", "knife", "mixer", "stand mixer", "kitchenaid"],
        "appliance": ["dishwasher", "refrigerator", "washer", "dryer", "vacuum", "cleaner"],
        "furniture": ["chair", "table", "sofa", "bed", "desk", "bookshelf", "dresser"],
        "home_decor": ["lamp", "curtain", "rug", "pillow", "candle", "frame", "hue"],
        
        # Fashion & Personal
        "clothing": ["shirt", "pants", "dress", "jeans", "jacket", "sweater", "hoodie"],
        "shoes": ["shoes", "sneakers", "boots", "sandals", "heels", "running shoes"],
        "accessories": ["watch", "jewelry", "bag", "wallet", "belt", "hat"],
        "beauty": ["makeup", "skincare", "perfume", "cosmetics", "shampoo", "lotion"],
        
        # Sports & Recreation
        "sports": ["bike", "bicycle", "treadmill", "weights", "yoga mat", "tennis"],
        "outdoor": ["tent", "backpack", "sleeping bag", "hiking", "camping"],
        "fitness": ["protein", "supplement", "gym equipment", "dumbbells"],
        
        # Toys & Kids
        "toys": ["toy", "lego", "doll", "action figure", "puzzle", "board game", "monopoly", "barbie", "creator"],
        "baby": ["baby", "stroller", "car seat", "diaper", "formula", "crib", "einstein", "activity table", "fisher-price"],
        "kids": ["children", "kids", "youth", "toddler"],
        
        # Automotive
        "automotive": ["tire", "battery", "oil", "filter", "brake", "car part"],
        "car_accessories": ["car charger", "phone mount", "seat cover", "floor mat"],
        
        # Books & Media
        "books": ["book", "novel", "textbook", "ebook", "kindle book", "gatsby", "programming"],
        "media": ["movie", "dvd", "blu-ray", "cd", "vinyl", "music"],
        "games": ["video game", "ps5", "xbox", "nintendo", "pc game", "call of duty", "modern warfare", "game"],
        
        # Office & Business
        "office": ["printer", "scanner", "paper", "pen", "notebook", "calculator"],
        "business": ["briefcase", "organizer", "label maker", "shredder"],
        
        # Health & Wellness
        "health": ["vitamins", "medicine", "thermometer", "blood pressure", "scale"],
        "personal_care": ["toothbrush", "razor", "hair dryer", "trimmer"]
    }
    
    def detect_category(self, title: str, content: str = "") -> str:
        """
        Detect product category from title and content
        
        Args:
            title: Product title
            content: Additional content text
            
        Returns:
            str: Detected category or "general" if unknown
        """
        text = (title + " " + content).lower()
        
        # Count keyword matches for each category with preference for exact matches
        category_scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in text:
                    # Boost score for exact word matches vs substring matches
                    if f" {keyword} " in f" {text} " or text.startswith(keyword) or text.endswith(keyword):
                        score += 2  # Exact word match
                    else:
                        score += 1  # Substring match
            
            if score > 0:
                category_scores[category] = score
        
        if not category_scores:
            return "general"
        
        # Return category with highest score
        return max(category_scores.items(), key=lambda x: x[1])[0]


class DynamicSpecExtractor:
    """Extracts specifications dynamically based on content patterns"""
    
    # Universal patterns that work across all product categories
    UNIVERSAL_SPEC_PATTERNS = {
        # Dimensions (any product)
        "dimensions": [
            r"(\d+\.?\d*)\s*[x×]\s*(\d+\.?\d*)\s*[x×]\s*(\d+\.?\d*)\s*(inches?|in|cm|mm)",
            r"dimensions?:?\s*(\d+\.?\d*)\s*[x×]\s*(\d+\.?\d*)\s*[x×]\s*(\d+\.?\d*)\s*(inches?|in|cm|mm)",
        ],
        "weight": [
            r"(\d+\.?\d*)\s*(lbs?|pounds?|kg|grams?|g|oz)\s*(?:weight)?",
            r"weight:?\s*(\d+\.?\d*)\s*(lbs?|pounds?|kg|grams?|g|oz)",
        ],
        "color": [
            r"color:?\s*([a-zA-Z\s\-]+)",
            r"available in\s+([a-zA-Z\s\-,]+)",
        ],
        "material": [
            r"material:?\s*([a-zA-Z\s\-]+)",
            r"made (?:of|from)\s+([a-zA-Z\s\-]+)",
        ],
        
        # Size (clothing, general)
        "size": [
            r"size:?\s*(XS|S|M|L|XL|XXL|XXXL|\d+[A-Z]?|Small|Medium|Large|Extra Large)",
            r"(?:mens?|womens?|kids?)\s+size\s+(XS|S|M|L|XL|XXL|XXXL|\d+[A-Z]?|Small|Medium|Large|Extra Large)",
        ],
        
        # Electronics specs
        "battery": [
            r"(\d+)\s*(mah|wh|hours?)\s*(?:battery)?",
            r"battery:?\s*(\d+)\s*(mah|wh|hours?)",
        ],
        "memory": [
            r"(\d+)\s*(gb|tb)\s*(ram|memory|storage)",
            r"(?:ram|memory|storage):?\s*(\d+)\s*(gb|tb)",
        ],
        "screen": [
            r"(\d+\.?\d*)[\"\'′]?\s*(?:inch)?\s*(?:screen|display|monitor)",
            r"(?:screen|display):?\s*(\d+\.?\d*)[\"\'′]?",
        ],
        "resolution": [
            r"(\d+)\s*[x×]\s*(\d+)\s*(?:pixels?|resolution)?",
            r"(?:resolution):?\s*(\d+)\s*[x×]\s*(\d+)",
        ],
        
        # Kitchen specs
        "capacity": [
            r"(\d+\.?\d*)\s*(cups?|liters?|l|quarts?|qt|oz|ml)\s*(?:capacity)?",
            r"capacity:?\s*(\d+\.?\d*)\s*(cups?|liters?|l|quarts?|qt|oz|ml)",
        ],
        "power": [
            r"(\d+)\s*(watts?)",
            r"power:?\s*(\d+)\s*(watts?)",
        ],
        
        # Book specs
        "pages": [
            r"(\d+)\s*pages?",
            r"pages?:?\s*(\d+)",
        ],
        "isbn": [
            r"isbn[-:]?\s*(\d{10}|\d{13})",
            r"(\d{13}|\d{10})",  # Standalone ISBN
        ],
        
        # Age/rating specs  
        "age": [
            r"(?:ages?|for)\s+(\d+\+?)",
            r"(\d+)\s*(?:years?|yr)\s*(?:and up|plus|\+)?",
        ],
        
        # Count/quantity specs
        "pieces": [
            r"(\d+,?\d*)\s*(?:pieces?|pcs?|parts?)",
            r"(?:pieces?|pcs?):?\s*(\d+,?\d*)",
        ],
    }
    
    def extract_specs(self, content: str, category: str) -> Dict[str, Any]:
        """
        Extract specifications from content using dynamic patterns
        
        Args:
            content: Text content to extract from
            category: Detected product category
            
        Returns:
            Dict[str, Any]: Extracted specifications
        """
        specs = {}
        
        # Apply universal patterns
        for spec_type, patterns in self.UNIVERSAL_SPEC_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    specs[spec_type] = self._process_pattern_match(spec_type, matches[0])
                    break  # Use first successful match
        
        # Category-specific extractions
        if category in ["laptop", "smartphone", "tablet"]:
            specs.update(self._extract_tech_specs(content))
        elif category in ["kitchen", "appliance"]:
            specs.update(self._extract_kitchen_specs(content))
        elif category in ["clothing", "shoes"]:
            specs.update(self._extract_fashion_specs(content))
        elif category in ["toys", "games"]:
            specs.update(self._extract_toy_specs(content))
            
        return specs
    
    def _process_pattern_match(self, spec_type: str, match: Any) -> Any:
        """Process regex match based on specification type"""
        if isinstance(match, tuple):
            if spec_type == "dimensions":
                return f"{match[0]}×{match[1]}×{match[2]} {match[3]}"
            elif spec_type == "weight":
                return f"{match[0]} {match[1]}"
            elif spec_type in ["battery", "memory", "capacity", "power"]:
                return f"{match[0]} {match[1]}"
            elif spec_type == "resolution":
                return f"{match[0]}×{match[1]}"
            else:
                return " ".join(str(m) for m in match if m).strip()
        return str(match).strip()
    
    def _extract_tech_specs(self, content: str) -> Dict[str, Any]:
        """Extract technology-specific specifications"""
        specs = {}
        
        # Processor/CPU
        cpu_patterns = [
            r"(?:cpu|processor):?\s*([a-zA-Z0-9\s\-]+(?:core|GHz|ghz))",
            r"(intel|amd|apple|snapdragon|mediatek)\s+([a-zA-Z0-9\s\-]+)",
        ]
        for pattern in cpu_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                specs["processor"] = match.group(0).strip()
                break
        
        # GPU/Graphics
        gpu_patterns = [
            r"(?:gpu|graphics):?\s*([a-zA-Z0-9\s\-]+)",
            r"(nvidia|amd|intel)\s+(rtx|gtx|radeon|arc)\s*([a-zA-Z0-9\s\-]+)",
        ]
        for pattern in gpu_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                specs["graphics"] = match.group(0).strip()
                break
                
        return specs
    
    def _extract_kitchen_specs(self, content: str) -> Dict[str, Any]:
        """Extract kitchen appliance specifications"""
        specs = {}
        
        # Speed settings
        speed_match = re.search(r"(\d+)\s*speeds?", content, re.IGNORECASE)
        if speed_match:
            specs["speeds"] = int(speed_match.group(1))
            
        # Timer
        timer_match = re.search(r"(\d+)\s*(?:minute|min|hour|hr)\s*timer", content, re.IGNORECASE)
        if timer_match:
            specs["timer"] = timer_match.group(0)
            
        return specs
    
    def _extract_fashion_specs(self, content: str) -> Dict[str, Any]:
        """Extract clothing and fashion specifications"""
        specs = {}
        
        # Fit type
        fit_patterns = [
            r"(slim|regular|loose|relaxed|athletic|skinny|straight|bootcut)\s*fit",
            r"fit:?\s*(slim|regular|loose|relaxed|athletic|skinny|straight|bootcut)",
        ]
        for pattern in fit_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                specs["fit"] = match.group(1).lower()
                break
        
        # Gender
        gender_patterns = [
            r"(mens?|womens?|unisex|boys?|girls?)",
            r"for\s+(men|women|boys?|girls?)",
        ]
        for pattern in gender_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                specs["gender"] = match.group(1).lower()
                break
                
        return specs
    
    def _extract_toy_specs(self, content: str) -> Dict[str, Any]:
        """Extract toy and game specifications"""
        specs = {}
        
        # Number of players
        players_match = re.search(r"(\d+)[-\s]*(\d+)?\s*players?", content, re.IGNORECASE)
        if players_match:
            if players_match.group(2):
                specs["players"] = f"{players_match.group(1)}-{players_match.group(2)}"
            else:
                specs["players"] = players_match.group(1)
        
        # Theme/franchise
        themes = ["star wars", "marvel", "disney", "pokemon", "minecraft", "harry potter"]
        for theme in themes:
            if theme in content.lower():
                specs["theme"] = theme.title()
                break
                
        return specs


class UniversalUnitNormalizer:
    """Normalizes units across different measurement systems"""
    
    def normalize_specs(self, specs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize units in specifications
        
        Args:
            specs: Raw specifications dictionary
            
        Returns:
            Dict[str, Any]: Normalized specifications
        """
        normalized = {}
        
        for key, value in specs.items():
            if isinstance(value, str):
                normalized[key] = self._normalize_string_value(key, value)
            else:
                normalized[key] = value
                
        return normalized
    
    def _normalize_string_value(self, key: str, value: str) -> Any:
        """Normalize a string value based on the key type"""
        value_lower = value.lower()
        
        # Weight normalization
        if "weight" in key:
            return self._normalize_weight(value_lower)
        
        # Memory/Storage normalization  
        elif any(term in key for term in ["memory", "storage", "ram"]):
            return self._normalize_memory(value_lower)
        
        # Battery normalization
        elif "battery" in key:
            return self._normalize_battery(value_lower)
        
        # Dimension normalization
        elif "dimension" in key:
            return self._normalize_dimensions(value_lower)
        
        # Default: return as-is
        return value
    
    def _normalize_weight(self, value: str) -> str:
        """Normalize weight to kg"""
        # Extract number and unit
        match = re.search(r'(\d+\.?\d*)\s*(lbs?|pounds?|kg|g|grams?|oz)', value)
        if not match:
            return value
            
        number, unit = float(match.group(1)), match.group(2)
        
        # Convert to kg
        if unit in ['lbs', 'lb', 'pounds', 'pound']:
            kg = number * 0.453592
        elif unit in ['g', 'grams', 'gram']:
            kg = number / 1000
        elif unit in ['oz']:
            kg = number * 0.0283495
        else:  # Already kg
            kg = number
            
        return f"{kg:.2f} kg"
    
    def _normalize_memory(self, value: str) -> str:
        """Normalize memory/storage to GB"""
        match = re.search(r'(\d+\.?\d*)\s*(gb|tb|mb)', value)
        if not match:
            return value
            
        number, unit = float(match.group(1)), match.group(2)
        
        # Convert to GB
        if unit == 'tb':
            gb = number * 1024
        elif unit == 'mb':
            gb = number / 1024
        else:  # Already GB
            gb = number
            
        return f"{int(gb)} GB"
    
    def _normalize_battery(self, value: str) -> str:
        """Keep battery units as-is (mAh for phones, Wh for laptops)"""
        return value
    
    def _normalize_dimensions(self, value: str) -> str:
        """Normalize dimensions to inches"""
        # Convert cm to inches if needed
        if 'cm' in value:
            match = re.search(r'(\d+\.?\d*)×(\d+\.?\d*)×(\d+\.?\d*)\s*cm', value)
            if match:
                cm_values = [float(match.group(i)) for i in range(1, 4)]
                inch_values = [cm / 2.54 for cm in cm_values]
                return f"{inch_values[0]:.1f}×{inch_values[1]:.1f}×{inch_values[2]:.1f} inches"
        
        return value


class SpecExtractorAgent(SmartShopperAgent):
    """
    Universal product specification extractor for any e-commerce category
    
    Extracts structured product data from credibility-filtered content using:
    - Dynamic pattern recognition for specs
    - Category-agnostic approach  
    - LLM enhancement for missing fields
    - Universal unit normalization
    """
    
    name = "Spec Extractor"
    color = SmartShopperAgent.YELLOW
    
    def __init__(self):
        super().__init__()
        self.category_detector = UniversalCategoryDetector()
        self.spec_extractor = DynamicSpecExtractor()
        self.unit_normalizer = UniversalUnitNormalizer()
        
        # Initialize LLM for enhancement
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.1,  # Low temperature for consistent extraction
            api_key=settings.OPENAI_API_KEY
        )
        
        # Coverage thresholds
        self.min_coverage_threshold = 0.6  # 60% minimum
        self.llm_enhancement_threshold = 0.4  # Use LLM if below 40%
        
        self.log("Initialized SpecExtractorAgent")
    
    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """
        Main processing method for product specification extraction
        """
        start_time = datetime.now()
        self.log("Starting product specification extraction")
        
        try:
            # Get credibility-filtered results
            credibility_results = state.get("credibility_filtered_results", [])
            search_query = state.get("search_query")
            
            if not credibility_results:
                self.log("No credibility-filtered results to process")
                state["structured_products"] = []
                return self._record_execution(state, start_time, 0, "success")
            
            intent = search_query.intent if search_query else "product_search"
            self.log(f"Processing {len(credibility_results)} results for intent: {intent}")
            
            # Extract specifications from each result
            structured_products = []
            for i, result in enumerate(credibility_results):
                try:
                    product_spec = await self._extract_product_specs(result, intent)
                    if product_spec:
                        structured_products.append(product_spec)
                        self.log(f"Extracted specs for result {i+1}: {product_spec.get('title', 'Unknown')[:50]}...")
                except Exception as e:
                    self.log(f"Failed to extract specs for result {i+1}: {e}")
                    continue
            
            # Update state
            state["structured_products"] = structured_products
            
            # Log results
            total_products = len(structured_products)
            avg_coverage = sum(p.get("extraction_coverage", 0) for p in structured_products) / max(total_products, 1)
            self.log(f"Extracted {total_products} products (avg coverage: {avg_coverage:.3f})")
            
            return self._record_execution(state, start_time, total_products, "success")
            
        except Exception as e:
            self.log(f"Error in specification extraction: {e}")
            # Graceful degradation - pass through empty results
            state["structured_products"] = []
            return self._record_execution(state, start_time, 0, "error", str(e))
    
    async def _extract_product_specs(self, result: Dict[str, Any], _intent: str) -> Optional[Dict[str, Any]]:
        """
        Extract specifications from a single credibility-filtered result
        """
        url = result.get("url", "")
        title = result.get("title", "")
        content = result.get("content", "")
        
        if not title and not content:
            return None
        
        # 1. Detect product category
        category = self.category_detector.detect_category(title, content)
        
        # 2. Extract basic product information
        basic_info = self._extract_basic_info(result)
        
        # 3. Extract specifications using pattern matching
        specs = self.spec_extractor.extract_specs(content, category)
        
        # 4. Normalize units
        specs = self.unit_normalizer.normalize_specs(specs)
        
        # 5. Calculate initial coverage
        coverage = self._calculate_coverage(basic_info, specs, category)
        
        # 6. LLM enhancement if coverage is low
        extraction_method = "pattern_matching"
        if coverage < self.llm_enhancement_threshold:
            try:
                enhanced_specs = await self._enhance_with_llm(basic_info, specs, content, category)
                if enhanced_specs:
                    specs.update(enhanced_specs)
                    coverage = self._calculate_coverage(basic_info, specs, category)
                    extraction_method = "hybrid"
                    self.log(f"LLM enhancement improved coverage to {coverage:.3f}")
            except Exception as e:
                self.log(f"LLM enhancement failed: {e}")
        
        # 7. Create final product specification  
        product_spec = {
            "title": basic_info.get("title", ""),
            "brand": basic_info.get("brand"),
            "price": basic_info.get("price"),
            "currency": basic_info.get("currency"),
            "availability": basic_info.get("availability"),
            "category": category,
            "specs": specs,
            "url": url,  # Primary URL field for user navigation
            "source_url": url,  # Keep for backward compatibility
            "domain": basic_info.get("domain", ""),  # Add domain field
            "extraction_coverage": coverage,
            "extraction_method": extraction_method,
            "images": basic_info.get("images", []),
            # Preserve credibility data from credibility filter
            "credibility_score": result.get("credibility_score", 0.0),
            "credibility_breakdown": result.get("credibility_breakdown", {})
        }
        
        return product_spec
    
    def _extract_basic_info(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic product information from result"""
        title = result.get("title", "").strip()
        content = result.get("content", "")
        url = result.get("url", "")
        
        # Extract domain from URL
        domain = ""
        if url:
            from urllib.parse import urlparse
            try:
                domain = urlparse(url).netloc
            except Exception:
                domain = ""
        
        # Extract brand from title (first word often is brand)
        brand = None
        if title:
            title_words = title.split()
            # Common brand indicators
            if title_words and len(title_words[0]) > 2:
                brand = title_words[0]
        
        # Extract price information
        price_info = self._extract_price_info(content)
        
        # If no price found and we have a URL, try title-based extraction as fallback
        if not price_info and title:
            price_info = self._extract_price_from_title_context(title, content)
        
        basic_info = {
            "title": title,
            "brand": brand,
            "url": url,  # Preserve original URL
            "domain": domain,  # Extract domain for credibility scoring
            "images": []  # Could be extracted from content if needed
        }
        
        # Add price information if found
        if price_info:
            basic_info.update(price_info)
        
        return basic_info
    
    def _extract_price_info(self, content: str) -> Dict[str, Any]:
        """
        Enhanced price extraction using comprehensive currency patterns
        Based on RSS price extraction patterns for better accuracy
        """
        price_info = {}
        
        # Comprehensive currency-specific patterns (most specific first)
        # Aligned with RSS price extraction patterns for consistency
        price_patterns = [
            # More specific currency symbols first (to avoid conflicts)
            # CAD patterns (must come before USD $)
            (r'C\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "CAD"),  # C$1,299.99
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*CAD', "CAD"),  # 1299.99 CAD
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*canadian', "CAD"),  # 1299.99 canadian
            
            # AUD patterns (must come before USD $)
            (r'A\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "AUD"),  # A$1,299.99
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*AUD', "AUD"),  # 1299.99 AUD
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*australian', "AUD"),  # 1299.99 australian
            
            # HKD patterns (must come before USD $)
            (r'HK\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "HKD"),  # HK$9,999.99
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*HKD', "HKD"),  # 9999.99 HKD
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*hong\s*kong', "HKD"),  # 9999.99 hong kong
            
            # SGD patterns (must come before USD $)
            (r'S\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "SGD"),  # S$1,299.99
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*SGD', "SGD"),  # 1299.99 SGD
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*singapore', "SGD"),  # 1299.99 singapore
            
            # NZD patterns (must come before USD $)
            (r'NZ\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "NZD"),  # NZ$1,299.99
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*NZD', "NZD"),  # 1299.99 NZD
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*new\s*zealand', "NZD"),  # 1299.99 new zealand
            
            # USD patterns (generic $ symbol - comes after specific ones)
            (r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD"),  # $1,299.99, $99.99
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*USD', "USD"),  # 1299.99 USD
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:usd|dollars?)', "USD"),  # 99 dollars
            
            # EUR patterns (handle European decimal formats)
            (r'€(\d{1,3}(?:[,.\s]\d{3})*(?:[,\.]\d{2})?)', "EUR"),  # €1.299,99, €99,99
            (r'(\d{1,3}(?:[,.\s]\d{3})*(?:[,\.]\d{2})?)\s*EUR', "EUR"),  # 1299.99 EUR
            (r'(\d{1,3}(?:[,.\s]\d{3})*(?:[,\.]\d{2})?)\s*€', "EUR"),  # 1299.99 €
            (r'(\d{1,3}(?:[,.\s]\d{3})*(?:[,\.]\d{2})?)\s*(?:eur|euros?)', "EUR"),  # 99 euros
            
            # GBP patterns
            (r'£(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "GBP"),  # £1,299.99
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*GBP', "GBP"),  # 1299.99 GBP
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:gbp|pounds?)', "GBP"),  # 99 pounds
            
            # JPY patterns
            (r'¥(\d{1,3}(?:,\d{3})*)', "JPY"),  # ¥99,999
            (r'(\d{1,3}(?:,\d{3})*)\s*JPY', "JPY"),  # 99999 JPY
            (r'(\d{1,3}(?:,\d{3})*)\s*¥', "JPY"),  # 99999 ¥
            (r'(\d{1,3}(?:,\d{3})*)\s*(?:jpy|yen)', "JPY"),  # 99999 yen
            
            # INR patterns
            (r'₹(\d{1,2}(?:,\d{2})*(?:,\d{3})(?:\.\d{2})?)', "INR"),  # ₹99,999.99
            (r'(\d{1,2}(?:,\d{2})*(?:,\d{3})(?:\.\d{2})?)\s*INR', "INR"),  # 99,999.99 INR
            (r'(\d{1,2}(?:,\d{2})*(?:,\d{3})(?:\.\d{2})?)\s*₹', "INR"),  # 99,999.99 ₹
            (r'(\d{1,2}(?:,\d{2})*(?:,\d{3})(?:\.\d{2})?)\s*(?:inr|rupees?)', "INR"),  # 99999 rupees
            (r'Rs\.?\s*(\d{1,2}(?:,\d{2})*(?:,\d{3})(?:\.\d{2})?)', "INR"),  # Rs. 99,999.99
            
            # CHF patterns
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*CHF', "CHF"),  # 1299.99 CHF
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:chf|swiss)', "CHF"),  # 1299.99 swiss
            
            # CNY patterns
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*CNY', "CNY"),  # 8999.99 CNY
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:cny|yuan|rmb)', "CNY"),  # 8999.99 yuan
            
            # KRW patterns
            (r'₩(\d{1,3}(?:,\d{3})*)', "KRW"),  # ₩1,299,999 (no decimals)
            (r'(\d{1,3}(?:,\d{3})*)\s*KRW', "KRW"),  # 1299999 KRW
            (r'(\d{1,3}(?:,\d{3})*)\s*₩', "KRW"),  # 1299999 ₩
            (r'(\d{1,3}(?:,\d{3})*)\s*(?:krw|won)', "KRW"),  # 1299999 won
            
            # SEK patterns
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*SEK', "SEK"),  # 12999.99 SEK
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:sek|krona)', "SEK"),  # 12999.99 krona
            
            # NOK patterns
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*NOK', "NOK"),  # 12999.99 NOK
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:nok|norwegian)', "NOK"),  # 12999.99 norwegian
            
            # DKK patterns
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*DKK', "DKK"),  # 9999.99 DKK
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:dkk|danish)', "DKK"),  # 9999.99 danish
            
            # ILS patterns
            (r'₪(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "ILS"),  # ₪4,999.99
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*ILS', "ILS"),  # 4999.99 ILS
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*₪', "ILS"),  # 4999.99 ₪
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:ils|shekel|shekels)', "ILS"),  # 4999.99 shekels
            
            # AED patterns
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*AED', "AED"),  # 4999.99 AED
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:aed|dirhams?)', "AED"),  # 4999.99 dirhams
            
            # Generic currency patterns (lower priority)
            (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:currency|price)', "USD"),  # fallback
        ]
        
        # Enhanced price extraction: Find ALL price matches and choose the best one
        all_price_candidates = []
        
        for pattern, currency in price_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                price_str = match.group(1).replace(' ', '')  # Remove spaces
                
                try:
                    # Handle European decimal format properly
                    if '.' in price_str and ',' in price_str:
                        # Check which separator is used as decimal
                        dot_pos = price_str.rfind('.')
                        comma_pos = price_str.rfind(',')
                        
                        if dot_pos < comma_pos:
                            # European format: 1.299,99 -> 1299.99
                            price_str = price_str.replace('.', '').replace(',', '.')
                        else:
                            # US format: 1,299.99 -> 1299.99
                            price_str = price_str.replace(',', '')
                    elif ',' in price_str:
                        # Check if comma is decimal separator (European) or thousands separator
                        parts = price_str.split(',')
                        if len(parts[-1]) == 2:  # Likely decimal: 1299,99
                            price_str = price_str.replace(',', '.')
                        else:  # Likely thousands separator: 1,299
                            price_str = price_str.replace(',', '')
                    
                    price = float(price_str)
                    
                    # Validate price range (avoid extracting years, IDs, etc.)
                    if 0.01 <= price <= 1000000:  # Reasonable price range
                        # Get context around the price for intelligent selection
                        start_pos = max(0, match.start() - 100)
                        end_pos = min(len(content), match.end() + 100)
                        context = content[start_pos:end_pos].lower()
                        
                        all_price_candidates.append({
                            'price': price,
                            'currency': currency,
                            'context': context,
                            'full_match': match.group(0),
                            'position': match.start()
                        })
                        
                except (ValueError, AttributeError):
                    continue
        
        # If we have multiple price candidates, choose the best one
        if all_price_candidates:
            best_price = self._select_best_price_candidate(all_price_candidates)
            if best_price:
                price_info["price"] = best_price['price']
                price_info["currency"] = best_price['currency']
        
        # Enhanced availability patterns
        availability_patterns = [
            r"(in stock|out of stock|available|unavailable|sold out|backordered|back-?ordered)",
            r"(pre-?order|pre-?sale|coming soon|temporarily unavailable)",
            r"ships? (?:in|within)\s+(\d+)\s*(days?|weeks?|months?)",
            r"(limited availability|limited stock|only \d+ left)",
            r"(add to cart|buy now|purchase|order now)",  # Positive availability indicators
        ]
        
        for pattern in availability_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                availability_text = match.group(0).strip().lower()
                
                # Normalize availability status
                if any(term in availability_text for term in ["in stock", "available", "add to cart", "buy now", "purchase", "order now"]):
                    price_info["availability"] = "in_stock"
                elif any(term in availability_text for term in ["out of stock", "sold out", "unavailable"]):
                    price_info["availability"] = "out_of_stock"
                elif any(term in availability_text for term in ["backorder", "back-order"]):
                    price_info["availability"] = "backordered"
                elif any(term in availability_text for term in ["pre-order", "pre-sale", "coming soon"]):
                    price_info["availability"] = "pre_order"
                elif "limited" in availability_text:
                    price_info["availability"] = "limited_stock"
                elif "ships" in availability_text or "days" in availability_text or "weeks" in availability_text:
                    price_info["availability"] = f"ships_{match.group(0).strip()}"
                else:
                    price_info["availability"] = availability_text
                break
        
        return price_info
    
    def _select_best_price_candidate(self, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Intelligently select the best price candidate from multiple matches.
        Prioritizes main product price over accessories, services, and related items.
        """
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Score each candidate based on context
        scored_candidates = []
        
        for candidate in candidates:
            score = 0
            context = candidate['context']
            price = candidate['price']
            
            # POSITIVE indicators (main product price)
            positive_indicators = [
                ('price', 10),  # Direct price mention
                ('buy', 8),     # Buy now, purchase
                ('add to cart', 8),
                ('our price', 8),
                ('sale price', 8),
                ('you save', 5),
                ('instant savings', 5),
                ('special', 3),
                ('offer', 3)
            ]
            
            # NEGATIVE indicators (not main price)
            negative_indicators = [
                ('protection plan', -15),  # Extended warranties
                ('warranty', -10),
                ('service', -10),
                ('plan', -8),
                ('add a', -8),           # "Add a protection plan"
                ('accessories', -10),
                ('related', -8),
                ('also available', -5),
                ('shipping', -12),       # Shipping costs
                ('tax', -10),           # Tax amounts
                ('deposit', -8),        # Security deposits
                ('monthly', -12),       # Monthly payments
                ('financing', -10),     # Financing amounts
                ('/mo', -12),           # Per month
                ('per month', -12),
                ('credit', -8),         # Credit card offers
                ('cashback', -5),       # Cashback amounts
                ('rebate', -5),         # Rebate amounts
            ]
            
            # Apply positive scoring
            for indicator, points in positive_indicators:
                if indicator in context:
                    score += points
            
            # Apply negative scoring  
            for indicator, points in negative_indicators:
                if indicator in context:
                    score += points  # points are already negative
            
            # Enhanced price range scoring (higher prices more likely to be main product for electronics)
            if price >= 3000:    # Premium product price (gaming laptops, high-end electronics)
                score += 25
            elif price >= 2000:  # High-end product price
                score += 20
            elif price >= 1000:  # Mid-to-high range product price
                score += 15
            elif price >= 500:   # Mid-range product price
                score += 10
            elif price >= 100:   # Low-end product or accessory
                score += 0  # Neutral
            elif price < 100:    # Very likely accessory/service price
                score -= 10
            elif price < 50:     # Almost certainly accessory/service price
                score -= 15
            
            # Position scoring (earlier prices often more prominent)
            if candidate['position'] < 1000:  # Early in content
                score += 3
            elif candidate['position'] < 5000:  # Middle of content
                score += 1
            
            scored_candidates.append((score, candidate))
        
        # Sort by score (highest first) and return the best candidate
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_candidate = scored_candidates[0][1]
        
        # Debug logging for development
        self.log(f"Price selection: Found {len(candidates)} candidates, chose ${best_candidate['price']:.2f} "
                f"(score: {scored_candidates[0][0]}) over others")
        
        return best_candidate
    
    def _extract_price_from_title_context(self, title: str, content: str) -> Dict[str, Any]:
        """
        Fallback price extraction focusing on title context and high-confidence patterns
        """
        price_info = {}
        
        # Combine title and content for analysis
        combined_text = f"{title} {content}"
        
        # High-confidence price patterns for fallback extraction
        fallback_patterns = [
            (r'\b(?:price|cost|priced\s+at)[:$\s]*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD"),
            (r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:each|ea\.?|price)', "USD"),
            (r'(?:starts\s+at|from|only)\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD"),
            # B&H Photo specific patterns
            (r'our\s+price\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD"),
            (r'sale\s+price\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', "USD"),
        ]
        
        for pattern, currency in fallback_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                try:
                    price_str = match.group(1).replace(',', '')
                    price = float(price_str)
                    
                    # Apply reasonable bounds for electronics
                    if 50 <= price <= 50000:
                        price_info["price"] = price
                        price_info["currency"] = currency
                        break
                except (ValueError, AttributeError):
                    continue
        
        return price_info
    
    def _calculate_coverage(self, basic_info: Dict[str, Any], specs: Dict[str, Any], category: str) -> float:
        """
        Calculate field coverage for extracted product data
        
        Args:
            basic_info: Basic product information
            specs: Extracted specifications
            category: Product category
            
        Returns:
            float: Coverage score (0.0 - 1.0)
        """
        # Universal required fields
        required_fields = ["title"]
        important_fields = ["brand", "price", "currency"]
        
        # Category-specific important fields
        category_important = {
            "laptop": ["processor", "memory", "storage", "screen"],
            "smartphone": ["memory", "battery", "screen", "camera"],
            "kitchen": ["capacity", "power", "material"],
            "clothing": ["size", "material", "color", "fit"],
            "toys": ["age", "pieces", "material"],
            "books": ["pages", "author", "isbn"],
        }
        
        # Calculate scores
        required_score = sum(1 for field in required_fields if basic_info.get(field)) / len(required_fields)
        
        universal_important = sum(1 for field in important_fields if basic_info.get(field))
        category_specific = sum(1 for field in category_important.get(category, []) if specs.get(field))
        
        total_important = len(important_fields) + len(category_important.get(category, []))
        important_score = (universal_important + category_specific) / max(total_important, 1)
        
        # Spec density bonus (more specs = better coverage)
        spec_count = len(specs)
        spec_bonus = min(0.2, spec_count * 0.02)  # Up to 20% bonus for 10+ specs
        
        # Final coverage calculation
        coverage = 0.6 * required_score + 0.3 * important_score + 0.1 + spec_bonus
        return min(1.0, coverage)
    
    async def _enhance_with_llm(
        self, 
        basic_info: Dict[str, Any], 
        existing_specs: Dict[str, Any], 
        content: str, 
        category: str
    ) -> Dict[str, Any]:
        """
        Use LLM to extract missing specifications
        """
        # Create category-adaptive prompt
        prompt = self._create_extraction_prompt(content, category, existing_specs)
        
        try:
            response = await self.llm.ainvoke(prompt)
            
            # Parse LLM response as JSON
            enhanced_specs = json.loads(response.content)
            
            # Validate and clean enhanced specs
            return self._validate_llm_specs(enhanced_specs, existing_specs)
            
        except json.JSONDecodeError:
            self.log("LLM returned invalid JSON, trying text parsing")
            return self._parse_llm_text_response(response.content)
        except Exception as e:
            self.log(f"LLM enhancement failed: {e}")
            return {}
    
    def _create_extraction_prompt(self, content: str, category: str, existing_specs: Dict[str, Any]) -> str:
        """Create LLM prompt for specification extraction"""
        
        category_hints = {
            "laptop": "processor/CPU, RAM, storage, screen size, graphics card, battery, weight, ports",
            "smartphone": "processor/chipset, RAM, storage, screen size, camera specs, battery, weight, OS",
            "kitchen": "capacity, power/wattage, material, dimensions, speed settings, safety features",
            "clothing": "size, material, color, fit type, care instructions, gender, style",
            "toys": "age range, dimensions, material, piece count, safety ratings, theme/brand",
            "furniture": "dimensions, material, weight capacity, color, assembly required, style",
            "automotive": "compatibility, dimensions, material, specifications, model numbers",
            "books": "pages, author, publisher, publication date, ISBN, format, genre",
            "general": "any relevant specifications, features, or technical details"
        }
        
        hint = category_hints.get(category, category_hints["general"])
        existing_list = ", ".join(existing_specs.keys()) if existing_specs else "none"
        
        prompt = f"""
Extract product specifications from this content. Focus on {category} products.

Content:
{content[:2000]}  # Limit content length

Already extracted: {existing_list}

For {category} products, look for: {hint}

Return ONLY a JSON object with new specifications (don't repeat existing ones):
{{
    "spec_name": "value",
    "another_spec": "value"
}}

Extract ANY specifications mentioned, even if unusual. Use clear, descriptive keys.
For measurements, include units (GB, inches, watts, etc.).
Return empty object {{}} if no new specs found.
"""
        
        return prompt
    
    def _validate_llm_specs(self, llm_specs: Dict[str, Any], existing_specs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean LLM-extracted specifications"""
        validated = {}
        
        for key, value in llm_specs.items():
            # Skip if already exists
            if key in existing_specs:
                continue
                
            # Clean key name
            clean_key = re.sub(r'[^\w\s_-]', '', str(key)).lower().replace(' ', '_')
            
            # Validate value
            if value and str(value).strip() and str(value).strip().lower() not in ['unknown', 'n/a', 'none']:
                validated[clean_key] = str(value).strip()
        
        return validated
    
    def _parse_llm_text_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response when JSON parsing fails"""
        specs = {}
        
        # Try to extract key-value pairs from text
        lines = response_text.split('\n')
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip(' -•*')
                    value = parts[1].strip()
                    if key and value:
                        clean_key = re.sub(r'[^\w\s_-]', '', key).lower().replace(' ', '_')
                        specs[clean_key] = value
        
        return specs
    
    def _record_execution(
        self, 
        state: SmartShopperWorkflowState, 
        start_time: datetime, 
        items_processed: int, 
        status: str,
        error_message: str = None
    ) -> SmartShopperWorkflowState:
        """Record agent execution in state"""
        execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        add_agent_step(
            state,
            self.name,
            status,
            execution_time,
            items_processed=items_processed,
            error_message=error_message
        )
        
        return state


# Factory function for easy instantiation
def create_spec_extractor_agent() -> SpecExtractorAgent:
    """Create SpecExtractorAgent instance"""
    return SpecExtractorAgent()