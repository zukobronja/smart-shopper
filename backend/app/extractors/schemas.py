"""
Schema validation for Tavily extraction results
Implements category-agnostic ecom_v1 and review_v1 schemas for ANY product type
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
from pydantic import BaseModel, Field, field_validator, ValidationError
from enum import Enum

logger = logging.getLogger(__name__)

class AvailabilityType(str, Enum):
    """Product availability states"""
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    PREORDER = "preorder"
    BACKORDER = "backorder"

class PageType(str, Enum):
    """Page types for extraction"""
    ECOM = "ecom"
    REVIEW = "review"

# Universal Product Schema Models (truly category-agnostic)
class ProductSpecs(BaseModel):
    """
    Dynamic product specifications for ANY product category
    Uses flexible key-value pairs instead of hardcoded fields
    LLM will determine appropriate specs based on product type
    """
    # Core universal attributes (minimal set)
    dimensions: Optional[str] = None
    weight: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    
    # Dynamic specifications as flexible dict
    # LLM will populate with category-appropriate fields:
    # - Electronics: cpu, ram_gb, battery_mah, screen_size_in
    # - Kitchen: capacity, power_watts, blade_material
    # - Books: pages, edition, isbn, publisher
    # - Furniture: weight_capacity, assembly_required, fabric_type
    # - Tools: voltage, torque, chuck_size, battery_type
    specifications: Dict[str, Any] = Field(default_factory=dict)
    
    # Meta information
    warranty: Optional[str] = None
    country_of_origin: Optional[str] = None
    model_year: Optional[int] = None
    
    class Config:
        extra = "allow"  # Allow any additional fields for maximum flexibility

class Product(BaseModel):
    """Product information - category agnostic"""
    title: str
    brand: Optional[str] = None
    model: Optional[str] = None
    sku: Optional[str] = None
    gtin: Optional[str] = None
    category: Optional[str] = None  # Flexible string - any category
    subcategory: Optional[str] = None
    product_type: Optional[str] = None
    images: Optional[List[str]] = Field(default_factory=list)
    specs: Optional[ProductSpecs] = Field(default_factory=ProductSpecs)
    description: Optional[str] = None
    features: Optional[List[str]] = Field(default_factory=list)

class Offer(BaseModel):
    """Product offer information"""
    price: Optional[float] = None
    currency: Optional[str] = None
    was_price: Optional[float] = None
    promo_text: Optional[str] = None
    availability: Optional[AvailabilityType] = None
    shipping_cost: Optional[float] = None
    delivery_eta: Optional[str] = None
    seller: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)
    review_count: Optional[int] = Field(None, ge=0)
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        if v and len(v) != 3:
            raise ValueError('Currency must be 3 characters')
        return v

class EcomV1(BaseModel):
    """ecom_v1 schema for e-commerce pages"""
    schema_version: str = "ecom_v1"
    url: str
    domain: str
    page_type: PageType = PageType.ECOM
    product: Product
    offer: Offer
    content_hash: Optional[str] = None
    extracted_at: str
    
    # Coverage metadata (computed)
    coverage_score: Optional[float] = None
    low_coverage: Optional[bool] = None
    missing_fields: Optional[List[str]] = Field(default_factory=list)

# Review Schema Models
class Review(BaseModel):
    """Review content"""
    headline: str
    author: Optional[str] = None
    published_at: Optional[str] = None
    updated_at: Optional[str] = None
    verdict_score: Optional[float] = Field(None, ge=0, le=10)
    pros: Optional[List[str]] = Field(default_factory=list)
    cons: Optional[List[str]] = Field(default_factory=list)
    summary: Optional[str] = None
    recommended_alternatives: Optional[List[str]] = Field(default_factory=list)
    product_refs: Optional[List[str]] = Field(default_factory=list)

class ReviewV1(BaseModel):
    """review_v1 schema for review pages"""
    schema_version: str = "review_v1"
    url: str
    domain: str
    page_type: PageType = PageType.REVIEW
    review: Review
    content_hash: Optional[str] = None
    extracted_at: str
    
    # Coverage metadata (computed)
    coverage_score: Optional[float] = None
    low_coverage: Optional[bool] = None
    missing_fields: Optional[List[str]] = Field(default_factory=list)

class SchemaValidator:
    """Schema validator with category-agnostic coverage computation"""
    
    def __init__(self):
        self.coverage_threshold = 0.60
        
        # Category-agnostic field importance weights
        self.ecom_field_weights = {
            # Critical fields (must have for basic functionality)
            'core': {
                'product.title': 3.0,
                'url': 2.0, 
                'domain': 2.0
            },
            # Important offer fields
            'offer': {
                'offer.price': 3.0,
                'offer.availability': 2.0,
                'offer.currency': 1.0
            },
            # Product identification
            'product': {
                'product.brand': 1.5,
                'product.model': 1.5,
                'product.category': 1.0,
                'product.sku': 1.0,
                'product.gtin': 1.0
            },
            # Specifications (any meaningful specs count)
            'specs': {
                # Weight specs based on having actual values, not specific fields
                'any_numeric_spec': 2.0,  # Any numeric specification
                'any_text_spec': 1.0,     # Any text specification
                'spec_count_bonus': 1.0   # Bonus for having multiple specs
            }
        }
        
        self.review_field_weights = {
            'core': {
                'review.headline': 3.0,
                'url': 2.0,
                'domain': 2.0
            },
            'content': {
                'review.pros': 2.0,
                'review.cons': 2.0, 
                'review.summary': 2.0,
                'review.verdict_score': 1.5,
                'review.author': 1.0,
                'review.published_at': 1.0
            }
        }
    
    def validate_ecom(self, data: Dict[str, Any]) -> Tuple[EcomV1, float, bool]:
        """
        Validate ecom_v1 schema and compute coverage
        
        Returns:
            (validated_model, coverage_score, is_low_coverage)
        """
        try:
            # First validate with Pydantic
            model = EcomV1(**data)
            
            # Compute coverage
            coverage_score, missing_fields = self._compute_ecom_coverage(model)
            is_low_coverage = coverage_score < self.coverage_threshold
            
            # Update model with coverage info
            model.coverage_score = coverage_score
            model.low_coverage = is_low_coverage
            model.missing_fields = missing_fields
            
            logger.info(f"Ecom validation: coverage={coverage_score:.2f}, low_coverage={is_low_coverage}")
            
            return model, coverage_score, is_low_coverage
            
        except ValidationError as e:
            logger.error(f"Ecom schema validation failed: {e}")
            raise
    
    def validate_review(self, data: Dict[str, Any]) -> Tuple[ReviewV1, float, bool]:
        """
        Validate review_v1 schema and compute coverage
        
        Returns:
            (validated_model, coverage_score, is_low_coverage)
        """
        try:
            # First validate with Pydantic
            model = ReviewV1(**data)
            
            # Compute coverage
            coverage_score, missing_fields = self._compute_review_coverage(model)
            is_low_coverage = coverage_score < self.coverage_threshold
            
            # Update model with coverage info
            model.coverage_score = coverage_score
            model.low_coverage = is_low_coverage
            model.missing_fields = missing_fields
            
            logger.info(f"Review validation: coverage={coverage_score:.2f}, low_coverage={is_low_coverage}")
            
            return model, coverage_score, is_low_coverage
            
        except ValidationError as e:
            logger.error(f"Review schema validation failed: {e}")
            raise
    
    def _compute_ecom_coverage(self, model: EcomV1) -> Tuple[float, List[str]]:
        """Compute category-agnostic coverage score for ecom data"""
        total_weight = 0.0
        present_weight = 0.0
        missing_fields = []
        
        # Core fields
        for field_path, weight in self.ecom_field_weights['core'].items():
            total_weight += weight
            if self._has_field_value(model, field_path):
                present_weight += weight
            else:
                missing_fields.append(field_path)
        
        # Offer fields
        for field_path, weight in self.ecom_field_weights['offer'].items():
            total_weight += weight
            if self._has_field_value(model, field_path):
                present_weight += weight
            else:
                missing_fields.append(field_path)
        
        # Product identification fields
        for field_path, weight in self.ecom_field_weights['product'].items():
            total_weight += weight
            if self._has_field_value(model, field_path):
                present_weight += weight
            else:
                missing_fields.append(field_path)
        
        # Dynamic specifications (truly category-agnostic approach)
        if model.product.specs:
            specs_model = model.product.specs.model_dump()
            
            # Count core universal fields
            universal_fields = ['dimensions', 'weight', 'material', 'color']
            universal_count = sum(1 for field in universal_fields 
                                if specs_model.get(field) is not None)
            
            # Count dynamic specifications
            dynamic_specs = specs_model.get('specifications', {})
            if isinstance(dynamic_specs, dict):
                numeric_specs = sum(1 for v in dynamic_specs.values() 
                                  if isinstance(v, (int, float)) and v is not None)
                text_specs = sum(1 for v in dynamic_specs.values() 
                               if isinstance(v, str) and v and v.strip())
                list_specs = sum(1 for v in dynamic_specs.values() 
                               if isinstance(v, list) and v)
                total_dynamic_specs = numeric_specs + text_specs + list_specs
            else:
                total_dynamic_specs = 0
                numeric_specs = text_specs = list_specs = 0
            
            # Award points for having specifications
            if total_dynamic_specs > 0:
                present_weight += self.ecom_field_weights['specs']['any_numeric_spec']
                total_weight += self.ecom_field_weights['specs']['any_numeric_spec']
            else:
                missing_fields.append('specs.dynamic_specifications')
                total_weight += self.ecom_field_weights['specs']['any_numeric_spec']
            
            if universal_count > 0:
                present_weight += self.ecom_field_weights['specs']['any_text_spec']
                total_weight += self.ecom_field_weights['specs']['any_text_spec']
            else:
                missing_fields.append('specs.universal_fields')
                total_weight += self.ecom_field_weights['specs']['any_text_spec']
            
            # Bonus for rich specification data
            if total_dynamic_specs >= 3 or universal_count >= 2:
                present_weight += self.ecom_field_weights['specs']['spec_count_bonus']
            total_weight += self.ecom_field_weights['specs']['spec_count_bonus']
        else:
            # No specs at all
            for spec_key in self.ecom_field_weights['specs']:
                total_weight += self.ecom_field_weights['specs'][spec_key]
                missing_fields.append(f'specs.{spec_key}')
        
        coverage_score = present_weight / total_weight if total_weight > 0 else 0.0
        return coverage_score, missing_fields
    
    def _compute_review_coverage(self, model: ReviewV1) -> Tuple[float, List[str]]:
        """Compute coverage score for review data"""
        total_weight = 0.0
        present_weight = 0.0
        missing_fields = []
        
        # Core fields
        for field_path, weight in self.review_field_weights['core'].items():
            total_weight += weight
            if self._has_field_value(model, field_path):
                present_weight += weight
            else:
                missing_fields.append(field_path)
        
        # Content fields
        for field_path, weight in self.review_field_weights['content'].items():
            total_weight += weight
            if self._has_field_value(model, field_path):
                present_weight += weight
            else:
                missing_fields.append(field_path)
        
        coverage_score = present_weight / total_weight if total_weight > 0 else 0.0
        return coverage_score, missing_fields
    
    def _has_field_value(self, model: BaseModel, field_path: str) -> bool:
        """Check if a nested field has a non-empty value"""
        try:
            parts = field_path.split('.')
            value = model
            
            for part in parts:
                value = getattr(value, part, None)
                if value is None:
                    return False
            
            # Check for empty lists/strings
            if isinstance(value, (list, str)) and len(value) == 0:
                return False
                
            return True
            
        except (AttributeError, TypeError):
            return False