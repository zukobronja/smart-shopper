#!/usr/bin/env python3
"""
Real Pipeline Integration Test: QueryOrchestrator -> TavilyRetriever -> CredibilityFilter

Tests the complete pipeline flow with real API calls to verify:
1. QueryOrchestrator produces proper search_query
2. TavilyRetriever produces raw_search_results and extracted_content  
3. CredibilityFilter processes and filters results properly
4. End-to-end state management works correctly
"""
import asyncio
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv('../../.env')

from app.config import settings
from app.agents.query_orchestrator_agent import QueryOrchestratorAgent
from app.agents.tavily_retriever_agent import TavilyRetrieverAgent
from app.agents.credibility_filter_agent import CredibilityFilterAgent
from app.agents.state import create_initial_state, get_state_summary


def check_api_keys():
    """Check if required API keys are available"""
    print("Checking API Keys...")
    
    openai_key = "Set" if settings.OPENAI_API_KEY else "Missing"
    tavily_key = "Set" if settings.TAVILY_API_KEY else "Missing"
    
    print(f"   OPENAI_API_KEY: {openai_key}")
    print(f"   TAVILY_API_KEY: {tavily_key}")
    
    if not settings.OPENAI_API_KEY or not settings.TAVILY_API_KEY:
        print("\nMissing required API keys!")
        return False
    
    print("All API keys configured")
    return True


async def test_three_agent_pipeline():
    """Test QueryOrchestrator -> TavilyRetriever -> CredibilityFilter pipeline"""
    print("\nTesting 3-Agent Pipeline Integration")
    print("=" * 60)
    
    # Initialize agents
    query_agent = QueryOrchestratorAgent()
    tavily_agent = TavilyRetrieverAgent()
    credibility_agent = CredibilityFilterAgent()
    
    print("Agents initialized")
    
    # Test with a typical product search query
    test_query = "best wireless earbuds under $150"
    print(f"\n Testing Query: '{test_query}'")
    
    # Create initial state
    state = create_initial_state(test_query, "pipeline_integration_test")
    print(f" Initial state created")
    
    try:
        # Step 1: QueryOrchestrator
        print("\n1. QueryOrchestrator Processing...")
        start_time = datetime.now()
        state = await query_agent.process(state)
        query_time = (datetime.now() - start_time).total_seconds()
        
        search_query = state.get("search_query")
        if not search_query:
            print("QueryOrchestrator failed")
            return False
            
        print(f" Query parsed ({query_time:.2f}s)")
        print(f"   Intent: {search_query.intent}")
        print(f"   Category: {search_query.category}")
        print(f"   Budget: ${search_query.budget_max}" if search_query.budget_max else "   Budget: None")
        
        # Step 2: TavilyRetriever  
        print("\n2. TavilyRetriever Processing...")
        start_time = datetime.now()
        state = await tavily_agent.process(state)
        tavily_time = (datetime.now() - start_time).total_seconds()
        
        raw_results = state.get("raw_search_results", [])
        extracted_content = state.get("extracted_content", [])
        
        if not raw_results:
            print("TavilyRetriever failed - no results")
            return False
            
        print(f" Tavily search completed ({tavily_time:.2f}s)")
        print(f"   Search results: {len(raw_results)}")
        print(f"   Extracted content: {len(extracted_content)}")
        print(f"   Coverage score: {state.get('coverage_score', 0.0):.2f}")
        
        # Step 3: CredibilityFilter
        print("\n3. CredibilityFilter Processing...")
        start_time = datetime.now()
        state = await credibility_agent.process(state)
        credibility_time = (datetime.now() - start_time).total_seconds()
        
        filtered_results = state.get("credibility_filtered_results", [])
        
        print(f" Credibility filtering completed ({credibility_time:.2f}s)")
        print(f"   Filtered results: {len(filtered_results)}")
        
        if filtered_results:
            # Show credibility scores
            scores = [r.get("credibility_score", 0) for r in filtered_results]
            avg_score = sum(scores) / len(scores)
            print(f"   Average credibility: {avg_score:.3f}")
            print(f"   Score range: {min(scores):.3f} - {max(scores):.3f}")
            
            # Show top result details
            top_result = filtered_results[0]
            print(f"\n Top Result:")
            print(f"   URL: {top_result.get('url', 'No URL')[:60]}...")
            print(f"   Title: {top_result.get('title', 'No title')[:50]}...")
            print(f"   Score: {top_result.get('credibility_score', 0):.3f}")
            
            # Show credibility breakdown
            breakdown = top_result.get('credibility_breakdown', {})
            if breakdown:
                print(f"   Domain: {breakdown.get('domain_score', 0):.3f}")
                print(f"   Recency: {breakdown.get('recency_score', 0):.3f}")
                print(f"   Extractability: {breakdown.get('extractability_score', 0):.3f}")
        
        # Overall pipeline summary
        total_time = query_time + tavily_time + credibility_time
        summary = get_state_summary(state)
        
        print(f"\n Pipeline Summary:")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Agents executed: {summary['progress']['agents_completed']}")
        print(f"   Total cost: ${summary['progress']['total_cost_usd']:.4f}")
        print(f"   Results: {len(raw_results)} -> {len(filtered_results)} (filtered)")
        
        return True
        
    except Exception as e:
        print(f" Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multiple_queries():
    """Test pipeline with different query types"""
    print("\nTesting Multiple Query Types")
    print("=" * 60)
    
    test_queries = [
        {
            "query": "iPhone 15 vs Samsung Galaxy S24 comparison",
            "expected_intent": "comparison",
            "expected_category": "smartphone"
        },
        {
            "query": "Sony WH-1000XM5 headphones review",
            "expected_intent": "review_search", 
            "expected_category": "headphones"
        },
        {
            "query": "gaming laptop RTX 4070 under $1800",
            "expected_intent": "product_search",
            "expected_category": "laptop"
        }
    ]
    
    # Initialize agents once
    query_agent = QueryOrchestratorAgent()
    tavily_agent = TavilyRetrieverAgent()
    credibility_agent = CredibilityFilterAgent()
    
    results = []
    
    for i, test_case in enumerate(test_queries, 1):
        print(f"\n{i}. Testing: '{test_case['query']}'")
        print("-" * 50)
        
        try:
            # Run pipeline
            state = create_initial_state(test_case["query"], f"multi_test_{i}")
            state = await query_agent.process(state)
            state = await tavily_agent.process(state)
            state = await credibility_agent.process(state)
            
            # Validate results
            search_query = state.get("search_query")
            filtered_results = state.get("credibility_filtered_results", [])
            
            intent_match = search_query.intent == test_case["expected_intent"]
            category_match = search_query.category == test_case["expected_category"]
            has_results = len(filtered_results) > 0
            
            print(f"   Intent: {search_query.intent} {'' if intent_match else ''}")
            print(f"   Category: {search_query.category} {'' if category_match else ''}")
            print(f"   Filtered results: {len(filtered_results)} {'' if has_results else ''}")
            
            if filtered_results:
                avg_score = sum(r.get("credibility_score", 0) for r in filtered_results) / len(filtered_results)
                print(f"   Avg credibility: {avg_score:.3f}")
            
            success = intent_match and category_match and has_results
            results.append({
                "query": test_case["query"],
                "success": success,
                "results_count": len(filtered_results)
            })
            
            print(f"   Status: {' SUCCESS' if success else ' FAILED'}")
            
        except Exception as e:
            print(f"    Error: {e}")
            results.append({"query": test_case["query"], "success": False, "error": str(e)})
    
    # Summary
    successful = sum(1 for r in results if r.get("success", False))
    print(f"\n Multi-Query Results:")
    print(f"   Success rate: {successful}/{len(results)} queries")
    
    return successful == len(results)


async def main():
    """Run all pipeline integration tests"""
    print("CredibilityFilter Pipeline Integration Tests")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Check prerequisites
    if not check_api_keys():
        return False
    
    try:
        # Test 1: Three-agent pipeline
        pipeline_success = await test_three_agent_pipeline()
        
        # Test 2: Multiple query types
        multi_query_success = await test_multiple_queries()
        
        # Final results
        print("\n" + "=" * 70)
        print("INTEGRATION TEST RESULTS")
        print("=" * 70)
        
        print(f" 3-Agent Pipeline: {'PASS' if pipeline_success else 'FAIL'}")
        print(f" Multi-Query Tests: {'PASS' if multi_query_success else 'FAIL'}")
        
        overall_success = pipeline_success and multi_query_success
        print(f"\n Overall Result: {'ALL TESTS PASSED' if overall_success else 'SOME TESTS FAILED'}")
        
        if overall_success:
            print("\nQueryOrchestrator -> TavilyRetriever -> CredibilityFilter pipeline is WORKING!")
            print("Real API integration functional")
            print("Multi-agent state management working")
            print("Credibility filtering operational")
            print("All query types handled correctly")
            print("\nReady to implement next agent: SpecExtractorAgent")
        else:
            print("\nSome issues detected in pipeline integration")
            print("Review the detailed output above for specific failures")
        
        return overall_success
        
    except Exception as e:
        print(f"\n Critical test failure: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
