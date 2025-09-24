"""
LLM-based extraction fallback for low-coverage Tavily results
Uses OpenAI to extract structured data with dynamic category-appropriate specifications
"""
from typing import Dict, Any, Optional
import logging
import json
from openai import OpenAI
from app.config import settings
from app.extractors.schemas import SchemaValidator, EcomV1, ReviewV1

logger = logging.getLogger(__name__)

class LLMExtractor:
    """LLM-based structured extraction with dynamic specifications"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = OpenAI(api_key=self.api_key)
        self.schema_validator = SchemaValidator()
        
        # Dynamic LLM extraction prompt for any product category
        self.ecom_prompt_template = """
You are a product data extraction expert. Extract structured information from this e-commerce page content.

IMPORTANT: Determine the product category first, then extract appropriate specifications for that category.

Return ONLY a valid JSON object with this structure:

{{
  "url": "string",
  "domain": "string", 
  "page_type": "ecom",
  "product": {{
    "title": "string (required)",
    "brand": "string or null",
    "model": "string or null",
    "category": "string (determine from content: electronics, furniture, clothing, kitchen, books, tools, etc.)",
    "subcategory": "string or null",
    "product_type": "string or null",
    "description": "string or null",
    "features": ["array of key features"],
    "specs": {{
      "dimensions": "string or null (e.g., '15.6 inches', '10x8x2 cm')",
      "weight": "string or null (e.g., '2.3 kg', '5.1 lbs')",
      "material": "string or null (e.g., 'aluminum', 'stainless steel')",
      "color": "string or null",
      "warranty": "string or null",
      "country_of_origin": "string or null",
      "model_year": "number or null",
      "specifications": {{
        // Add category-appropriate fields based on product type:
        // Electronics: "cpu", "ram_gb", "storage_gb", "battery_mah", "screen_size_in"
        // Kitchen: "capacity", "power_watts", "blade_material", "dishwasher_safe"
        // Furniture: "weight_capacity", "assembly_required", "fabric_type"
        // Books: "pages", "isbn", "publisher", "edition", "language"
        // Clothing: "size", "fabric_composition", "care_instructions"
        // Tools: "voltage", "torque", "chuck_size", "battery_type"
        // Plants: "light_requirements", "watering_frequency", "humidity"
        // etc.
      }}
    }}
  }},
  "offer": {{
    "price": "number or null",
    "currency": "string (3 chars) or null",
    "was_price": "number or null (original price if on sale)",
    "availability": "in_stock|out_of_stock|preorder|backorder or null",
    "rating": "number (0-5) or null",
    "review_count": "number or null",
    "seller": "string or null",
    "shipping_cost": "number or null"
  }},
  "extracted_at": "2025-09-19T08:30:00.000Z"
}}

GUIDELINES:
1. Identify product category from content (don't assume electronics)
2. Extract specifications relevant to that category
3. Use numeric values where possible (ram_gb: 16, not "16GB")
4. Include units in string fields where needed
5. Be accurate - only include data that's clearly stated

Content to extract from:
---
{content}
---

JSON:"""

        self.review_prompt_template = """
You are a review extraction expert. Extract structured information from this review page.

Return ONLY a valid JSON object with this structure:

{{
  "url": "string",
  "domain": "string",
  "page_type": "review",
  "review": {{
    "headline": "string (required - main review title)",
    "author": "string or null",
    "published_at": "ISO datetime string or null",
    "updated_at": "ISO datetime string or null", 
    "verdict_score": "number (0-10) or null (overall rating/score)",
    "pros": ["array of positive points"],
    "cons": ["array of negative points"],
    "summary": "string or null (key takeaway or conclusion)",
    "recommended_alternatives": ["array of alternative products mentioned"],
    "product_refs": ["array of specific product models/names mentioned"]
  }},
  "extracted_at": "2025-09-19T08:30:00.000Z"
}}

GUIDELINES:
1. Extract pros/cons as separate clear points
2. Convert any scores to 0-10 scale
3. Include publication date if mentioned
4. Capture main conclusion in summary

Content to extract from:
---
{content}
---

JSON:"""

    def extract_ecom_fallback(
        self,
        content: str,
        url: str,
        domain: str,
        max_tokens: int = 2500
    ) -> Optional[Dict[str, Any]]:
        """
        Extract e-commerce data using LLM with dynamic specifications
        
        Args:
            content: Raw content from crawl
            url: Source URL
            domain: Source domain
            max_tokens: Max tokens for LLM response
            
        Returns:
            Extracted ecom data or None if failed
        """
        try:
            logger.info(f"LLM ecom extraction for {url}")
            
            prompt = self.ecom_prompt_template.format(
                content=content[:6000]  # Limit content length for token efficiency
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.1,  # Low temperature for consistent extraction
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            extracted_data = json.loads(response_text)
            
            # Set/override required fields
            extracted_data["url"] = url
            extracted_data["domain"] = domain
            extracted_data["page_type"] = "ecom"
            extracted_data["extracted_at"] = "2025-09-19T08:30:00.000Z"
            
            logger.info(f"LLM ecom extraction successful for {url}")
            logger.info(f"Detected category: {extracted_data.get('product', {}).get('category', 'unknown')}")
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"LLM ecom extraction failed for {url}: {e}")
            return None
    
    def extract_review_fallback(
        self,
        content: str,
        url: str,
        domain: str,
        max_tokens: int = 2000
    ) -> Optional[Dict[str, Any]]:
        """
        Extract review data using LLM fallback
        
        Args:
            content: Raw content from crawl
            url: Source URL  
            domain: Source domain
            max_tokens: Max tokens for LLM response
            
        Returns:
            Extracted review data or None if failed
        """
        try:
            logger.info(f"LLM review extraction for {url}")
            
            prompt = self.review_prompt_template.format(
                content=content[:5000]  # Limit content length
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content.strip()
            extracted_data = json.loads(response_text)
            
            # Set/override required fields
            extracted_data["url"] = url
            extracted_data["domain"] = domain
            extracted_data["page_type"] = "review"
            extracted_data["extracted_at"] = "2025-09-19T08:30:00.000Z"
            
            logger.info(f"LLM review extraction successful for {url}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"LLM review extraction failed for {url}: {e}")
            return None
    
    def merge_extractions(
        self,
        tavily_data: Dict[str, Any],
        llm_data: Dict[str, Any],
        schema_type: str
    ) -> Dict[str, Any]:
        """
        Merge Tavily and LLM extraction results intelligently
        
        Strategy:
        - Prefer specific values over generic ones
        - Prefer numeric values over text descriptions  
        - Merge specifications dictionaries
        - Keep richer content from either source
        
        Args:
            tavily_data: Data from Tavily extract
            llm_data: Data from LLM fallback
            schema_type: "ecom_v1" or "review_v1"
            
        Returns:
            Merged data with best fields from both sources
        """
        try:
            logger.info(f"Merging {schema_type} extractions")
            
            # Start with Tavily data as base
            merged = tavily_data.copy()
            
            if schema_type == "ecom_v1":
                self._merge_ecom_fields(merged, llm_data)
            elif schema_type == "review_v1":
                self._merge_review_fields(merged, llm_data)
            
            # Add merge metadata
            merged["merge_notes"] = {
                "merged_from": ["tavily", "llm"],
                "merge_strategy": "intelligent_field_selection",
                "timestamp": "2025-09-19T08:30:00.000Z"
            }
            
            logger.info("Extraction merge completed")
            return merged
            
        except Exception as e:
            logger.error(f"Extraction merge failed: {e}")
            return tavily_data  # Fallback to Tavily data
    
    def _merge_ecom_fields(self, merged: Dict[str, Any], llm_data: Dict[str, Any]):
        """Merge ecom-specific fields intelligently"""
        llm_product = llm_data.get("product", {})
        llm_offer = llm_data.get("offer", {})
        llm_specs = llm_product.get("specs", {})
        
        # Merge product fields (prefer non-null values)
        merged_product = merged.get("product", {})
        for field in ["brand", "model", "category", "subcategory", "description", "features"]:
            if not merged_product.get(field) and llm_product.get(field):
                merged_product[field] = llm_product[field]
        
        # Merge specifications intelligently
        if "specs" in merged_product and llm_specs:
            merged_specs = merged_product["specs"]
            
            # Merge dynamic specifications dict
            llm_dynamic_specs = llm_specs.get("specifications", {})
            if llm_dynamic_specs and isinstance(llm_dynamic_specs, dict):
                if "specifications" not in merged_specs:
                    merged_specs["specifications"] = {}
                
                # Merge specification fields, preferring detailed values
                for spec_key, llm_value in llm_dynamic_specs.items():
                    if llm_value is not None and spec_key not in merged_specs["specifications"]:
                        merged_specs["specifications"][spec_key] = llm_value
        
        # Merge offer fields (prefer numeric prices and detailed availability)
        merged_offer = merged.get("offer", {})
        for field in ["price", "currency", "was_price", "availability", "rating", "review_count"]:
            if not merged_offer.get(field) and llm_offer.get(field):
                merged_offer[field] = llm_offer[field]
    
    def _merge_review_fields(self, merged: Dict[str, Any], llm_data: Dict[str, Any]):
        """Merge review-specific fields intelligently"""
        llm_review = llm_data.get("review", {})
        merged_review = merged.get("review", {})
        
        # Merge review fields, preferring detailed content
        for field in ["author", "published_at", "verdict_score", "summary"]:
            if not merged_review.get(field) and llm_review.get(field):
                merged_review[field] = llm_review[field]
        
        # Merge arrays (pros, cons, alternatives) by combining unique items
        for array_field in ["pros", "cons", "recommended_alternatives", "product_refs"]:
            merged_array = merged_review.get(array_field, [])
            llm_array = llm_review.get(array_field, [])
            
            if llm_array:
                # Combine and deduplicate
                combined = list(set(merged_array + llm_array))
                merged_review[array_field] = combined