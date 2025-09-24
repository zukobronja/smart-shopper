import pytest
from datetime import UTC, datetime

from app.agents.state import create_initial_state
from app.agents.rss_result_adapter import RSSResultAdapterAgent
from app.agents.result_fusion_agent import ResultFusionAgent


@pytest.mark.asyncio
async def test_rss_result_adapter_creates_structured_products():
    state = create_initial_state("test query")
    agent = RSSResultAdapterAgent()

    state["rss_results"] = [
        {
            "title": "Super Laptop Deal",
            "summary": "Great price on gaming laptop",
            "link": "https://example.com/deal1",
            "source_domain": "example.com",
            "feed_url": "https://example.com/rss",
            "feed_id": "123",
            "price": {"amount": 999.0, "currency": "USD"},
            "categories": ["electronics", "laptops"],
            "tags": ["gaming", "deal"],
            "published_at": datetime.now(UTC),
        }
    ]

    updated_state = await agent.process(state)

    adapted = updated_state["rss_structured_products"]
    assert len(adapted) == 1
    product = adapted[0]
    assert product["title"] == "Super Laptop Deal"
    assert product["price"] == 999.0
    assert product["currency"] == "USD"
    assert product["specs"]["summary"] == "Great price on gaming laptop"
    assert product["metadata"]["feed_id"] == "123"


@pytest.mark.asyncio
async def test_result_fusion_combines_and_dedupes():
    state = create_initial_state("test query")
    fusion_agent = ResultFusionAgent()

    state["structured_products"] = [
        {
            "title": "Super Laptop Deal",
            "source_url": "https://example.com/deal1",
            "price": 1200.0,
        }
    ]
    state["rss_structured_products"] = [
        {
            "title": "Super Laptop Deal",
            "source_url": "https://example.com/deal1",
            "price": 999.0,
        },
        {
            "title": "Wireless Headphones",
            "source_url": "https://example.com/deal2",
            "price": 149.0,
        },
    ]

    updated_state = await fusion_agent.process(state)
    fused = updated_state["structured_products"]

    assert len(fused) == 2
    titles = {item["title"] for item in fused}
    assert titles == {"Super Laptop Deal", "Wireless Headphones"}
