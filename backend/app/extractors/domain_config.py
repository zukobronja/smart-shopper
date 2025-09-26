"""
Domain configuration for Tavily integration
Defines trusted domains and search parameters by intent
"""
from typing import Dict, List, Any

# Trusted E-commerce Domains
TRUSTED_ECOM_DOMAINS = [
    "amazon.com", "bestbuy.com", "walmart.com", "target.com",
    "newegg.com", "bhphotovideo.com", "microcenter.com",
    "costco.com", "homedepot.com", "lowes.com",
    "staples.com", "officedepot.com", "macys.com",
    "nordstrom.com", "zappos.com", "wayfair.com",
    # European retailers
    "mediamarkt.de", "saturn.de", "otto.de",
    "argos.co.uk", "currys.co.uk", "johnlewis.com",
    # Asian retailers
    "rakuten.com", "yodobashi.com"
]

# Trusted Review Domains  
TRUSTED_REVIEW_DOMAINS = [
    "wirecutter.nytimes.com", "cnet.com", "techradar.com",
    "laptopmag.com", "tomshardware.com", "digitaltrends.com",
    "pcmag.com", "tomsguide.com", "anandtech.com",
    "androidcentral.com", "imore.com", "macrumors.com",
    "engadget.com", "theverge.com", "arstechnica.com",
    "consumerreports.org", "goodhousekeeping.com",
    "which.co.uk", "trustpilot.com"
]

# Trusted Comparison Domains
TRUSTED_COMPARISON_DOMAINS = [
    "versus.com", "gsmarena.com", "notebookcheck.net",
    "rtings.com", "displayspecifications.com",
    "cpubenchmark.net", "videocardbenchmark.net"
]

# Trusted News Domains  
TRUSTED_NEWS_DOMAINS = [
    "techcrunch.com", "wired.com", "reuters.com",
    "bloomberg.com", "wsj.com", "cnbc.com",
    "forbes.com", "businessinsider.com"
]

def get_domains_for_intent(intent: str) -> List[str]:
    """Get relevant domains based on search intent"""
    domain_mapping = {
        "product_search": TRUSTED_ECOM_DOMAINS,
        "review_search": TRUSTED_REVIEW_DOMAINS, 
        "comparison": TRUSTED_COMPARISON_DOMAINS,
        "news_search": TRUSTED_NEWS_DOMAINS,
        "general": TRUSTED_ECOM_DOMAINS + TRUSTED_REVIEW_DOMAINS
    }
    return domain_mapping.get(intent, TRUSTED_ECOM_DOMAINS)

def get_exclude_domains_for_intent(intent: str) -> List[str]:
    """Get domains to exclude based on search intent"""
    exclude_mapping = {
        "product_search": [
            # Exclude forums and user-generated content for product search
            "reddit.com", "quora.com", "stackoverflow.com",
            "facebook.com", "twitter.com", "instagram.com"
        ],
        "review_search": [
            # Exclude e-commerce for review-focused search
            "amazon.com", "ebay.com", "alibaba.com"
        ],
        "comparison": [
            # Exclude shopping sites for comparison search
            "amazon.com", "walmart.com", "target.com"
        ],
        "news_search": [
            # Exclude commercial sites for news search
            "amazon.com", "bestbuy.com", "walmart.com"
        ]
    }
    return exclude_mapping.get(intent, [])

def get_search_params_for_intent(intent: str, query: str) -> Dict[str, Any]:
    """Get optimized search parameters based on intent and query"""
    base_params = {
        "include_answer": False,        # Don't waste credits on answers
        "include_raw_content": False,   # Get content via extract instead  
        "auto_parameters": True         # Let Tavily optimize automatically
    }
    
    intent_configs = {
        "product_search": {
            "topic": "general",
            "time_range": "month",      # Recent products (valid: 'day', 'week', 'month', 'year')
            "search_depth": "advanced",
            "include_domains": get_domains_for_intent("product_search")[:10],  # Limit for API
            "exclude_domains": get_exclude_domains_for_intent("product_search")
        },
        "review_search": {
            "topic": "general", 
            "time_range": "year",       # Comprehensive reviews
            "search_depth": "advanced",
            "include_domains": get_domains_for_intent("review_search")[:10],
            "exclude_domains": get_exclude_domains_for_intent("review_search")
        },
        "comparison": {
            "topic": "general",
            "time_range": "month",      # Recent comparisons
            "search_depth": "advanced",
            "include_domains": get_domains_for_intent("comparison")[:10],
            "exclude_domains": get_exclude_domains_for_intent("comparison")
        },
        "news_search": {
            "topic": "news",
            "time_range": "week",       # Latest news
            "search_depth": "basic",    # News doesn't need deep crawling
            "include_domains": get_domains_for_intent("news_search")[:10],
            "exclude_domains": get_exclude_domains_for_intent("news_search")
        },
        "general": {
            "topic": "general",
            "time_range": "month",      # Recent general content
            "search_depth": "basic"     # Conservative for general search
        }
    }
    
    config = intent_configs.get(intent, intent_configs["general"])
    return {**base_params, **config}

def get_topic_for_intent(intent: str) -> str:
    """Get appropriate Tavily topic based on search intent"""
    topic_mapping = {
        "product_search": "general",
        "review_search": "general", 
        "comparison": "general",
        "news_search": "news",
        "finance_search": "finance",
        "general": "general"
    }
    return topic_mapping.get(intent, "general")

# Domains that block programmatic access (access denied/403 errors)
ACCESS_DENIED_DOMAINS = [
    "homedepot.com",  # Returns 403 for category pages
    "lowes.com",      # Similar access restrictions 
    "amazon.co.uk",   # Regional Amazon sites with stricter bot detection
    "walmart.ca",     # Canadian Walmart with access restrictions
]

def is_domain_blocked(url: str) -> bool:
    """Check if domain is known to block programmatic access"""
    if not url:
        return False
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        
        return any(blocked_domain in domain for blocked_domain in ACCESS_DENIED_DOMAINS)
    except Exception:
        return False

# Domain quality scoring weights
DOMAIN_QUALITY_SCORES = {
    # High-quality e-commerce (0.9-1.0)
    "amazon.com": 1.0,
    "bestbuy.com": 0.95,
    "walmart.com": 0.9,
    "target.com": 0.9,
    
    # High-quality reviews (0.85-0.95)
    "wirecutter.nytimes.com": 0.95,
    "consumerreports.org": 0.95,
    "cnet.com": 0.9,
    "techradar.com": 0.85,
    
    # Medium quality (0.7-0.85)
    "newegg.com": 0.8,
    "pcmag.com": 0.8,
    "digitaltrends.com": 0.75,
    
    # Lower quality but acceptable (0.5-0.7)
    "reddit.com": 0.6,
    "quora.com": 0.5
}

def get_domain_quality_score(domain: str) -> float:
    """Get quality score for a domain (0.0-1.0)"""
    # Remove www. prefix if present
    domain = domain.replace("www.", "")
    
    # Check exact match first
    if domain in DOMAIN_QUALITY_SCORES:
        return DOMAIN_QUALITY_SCORES[domain]
    
    # Check for subdomain matches
    for known_domain, score in DOMAIN_QUALITY_SCORES.items():
        if domain.endswith(known_domain):
            return score * 0.9  # Slightly lower for subdomains
    
    # Default score for unknown domains
    return 0.7