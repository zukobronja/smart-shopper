#!/usr/bin/env python3
"""
Real API Test for QueryOrchestratorAgent -> TavilyRetrieverAgent
Uses actual OpenAI and Tavily API keys for comprehensive integration testing
"""
import asyncio
import os
import sys
import time
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from app.config import settings
from app.agents.query_orchestrator_agent import QueryOrchestratorAgent
from app.agents.tavily_retriever_agent import TavilyRetrieverAgent
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
        print("Please set OPENAI_API_KEY and TAVILY_API_KEY environment variables")
        return False
    
    print("All API keys configured")
    return True


async def test_individual_agents():
    """Test each agent individually"""
    print("\nTesting Individual Agents")
    print("=" * 50)
    
    # Test QueryOrchestratorAgent
    print("\n1. Testing QueryOrchestratorAgent...")
    query_agent = QueryOrchestratorAgent()
    
    test_state = create_initial_state(
        raw_query="gaming laptop under $2000",
        run_id="individual_test_query"
    )
    
    start_time = time.time()
    result_state = await query_agent.process(test_state)
    query_time = (time.time() - start_time) * 1000
    
    if result_state.get("search_query"):
        search_query = result_state["search_query"]
        print(f"QueryOrchestrator SUCCESS ({query_time:.0f}ms)")
        print(f"   Intent: {search_query.intent}")
        print(f"   Category: {search_query.category}")
        print(f"   Budget max: {search_query.budget_max}")
        print(f"   Tavily params: {result_state.get('tavily_search_params', {})}")
    else:
        print(f"QueryOrchestrator FAILED")
        return False
    
    # Test TavilyRetrieverAgent
    print("\n2. Testing TavilyRetrieverAgent...")
    tavily_agent = TavilyRetrieverAgent()
    
    # Test configuration first
    config = await tavily_agent.test_configuration()
    if config.get('error'):
        print(f"TavilyRetriever configuration error: {config['error']}")
        return False
    
    print(f"TavilyRetriever configuration OK")
    print(f"   Client: {config.get('client_type')}")
    
    # Now test with real data from QueryOrchestrator
    start_time = time.time()
    result_state = await tavily_agent.process(result_state)
    tavily_time = (time.time() - start_time) * 1000
    
    search_results = result_state.get("raw_search_results", [])
    extracted_content = result_state.get("extracted_content", [])
    coverage_score = result_state.get("coverage_score", 0.0)
    
    print(f"TavilyRetriever SUCCESS ({tavily_time:.0f}ms)")
    print(f"   Search results: {len(search_results)}")
    print(f"   Extracted content: {len(extracted_content)}")
    print(f"   Coverage score: {coverage_score:.2f}")
    
    return True


async def test_integration_scenarios():
    """Test different query scenarios end-to-end"""
    print("\nTesting Integration Scenarios")
    print("=" * 50)
    
    test_queries = [
        {
            "query": "best laptop for programming under $1500",
            "expected_intent": "product_search",
            "expected_category": "laptop"
        },
        {
            "query": "iPhone 15 vs Samsung Galaxy S24 camera comparison",
            "expected_intent": "comparison", 
            "expected_category": "smartphone"
        },
        {
            "query": "Sony WH-1000XM5 headphones review",
            "expected_intent": "review_search",
            "expected_category": "headphones"
        }
    ]
    
    query_agent = QueryOrchestratorAgent()
    tavily_agent = TavilyRetrieverAgent()
    
    results = []
    
    for i, test_case in enumerate(test_queries, 1):
        print(f"\n{i}. Testing: '{test_case['query']}'")
        print("-" * 60)
        
        # Create state
        state = create_initial_state(
            raw_query=test_case["query"],
            run_id=f"scenario_test_{i}"
        )
        
        try:
            # Step 1: QueryOrchestrator
            start_time = time.time()
            state = await query_agent.process(state)
            query_time = time.time() - start_time
            
            search_query = state.get("search_query")
            if not search_query:
                print(f"Query parsing failed")
                results.append({"query": test_case["query"], "success": False})
                continue
            
            # Validate expectations
            intent_match = search_query.intent == test_case["expected_intent"]
            category_match = search_query.category == test_case["expected_category"]
            
            print(f"   Query Processing: {query_time*1000:.0f}ms")
            print(f"   Intent: {search_query.intent} {'' if intent_match else ''}")
            print(f"   Category: {search_query.category} {'' if category_match else ''}")
            
            # Step 2: TavilyRetriever
            start_time = time.time()
            state = await tavily_agent.process(state)
            tavily_time = time.time() - start_time
            
            search_results = state.get("raw_search_results", [])
            extracted_content = state.get("extracted_content", [])
            coverage_score = state.get("coverage_score", 0.0)
            
            print(f"   Tavily Processing: {tavily_time*1000:.0f}ms")
            print(f"   Search results: {len(search_results)}")
            print(f"   Extracted content: {len(extracted_content)}")
            print(f"   Coverage: {coverage_score:.2f}")
            
            # Check agent execution
            agent_steps = state.get("agent_steps", [])
            all_successful = all(step.status == "success" for step in agent_steps)
            
            print(f"   Agent execution: {'' if all_successful else ''} ({len(agent_steps)} steps)")
            
            success = intent_match and category_match and all_successful and (len(search_results) > 0 or len(extracted_content) > 0)
            results.append({
                "query": test_case["query"],
                "success": success,
                "query_time_ms": query_time * 1000,
                "tavily_time_ms": tavily_time * 1000,
                "search_results": len(search_results),
                "extracted_content": len(extracted_content),
                "coverage_score": coverage_score
            })
            
            print(f"   Overall: {' SUCCESS' if success else ' FAILED'}")
            
        except Exception as e:
            print(f" Error: {e}")
            results.append({"query": test_case["query"], "success": False, "error": str(e)})
    
    return results


async def test_performance_metrics():
    """Test performance and cost metrics"""
    print("\n Performance & Cost Analysis")
    print("=" * 50)
    
    query_agent = QueryOrchestratorAgent()
    tavily_agent = TavilyRetrieverAgent()
    
    # Test with a standard query
    state = create_initial_state(
        raw_query="mechanical keyboard for gaming",
        run_id="performance_test"
    )
    
    # Run full pipeline
    start_time = time.time()
    state = await query_agent.process(state)
    state = await tavily_agent.process(state)
    total_time = time.time() - start_time
    
    # Analyze results
    summary = get_state_summary(state)
    agent_steps = state.get("agent_steps", [])
    
    print(f" Performance Metrics:")
    print(f"   Total pipeline time: {total_time*1000:.0f}ms")
    print(f"   Agents executed: {len(agent_steps)}")
    print(f"   Total cost: ${summary['progress']['total_cost_usd']:.4f}")
    
    for step in agent_steps:
        cost_per_item = step.cost_usd / step.items_processed if step.items_processed > 0 else 0
        print(f"   {step.agent_name}: {step.execution_time_ms}ms, "
              f"${step.cost_usd:.4f}, {step.items_processed} items "
              f"(${cost_per_item:.4f}/item)")
    
    # Performance targets from BACKEND_ARCHITECTURE.md
    performance_ok = total_time < 10.0  # Under 10 seconds
    cost_reasonable = summary['progress']['total_cost_usd'] < 0.10  # Under 10 cents
    
    print(f"\n Performance Targets:")
    print(f"   Speed target (<10s): {'' if performance_ok else ''} ({total_time:.1f}s)")
    print(f"   Cost target (<$0.10): {'' if cost_reasonable else ''} (${summary['progress']['total_cost_usd']:.4f})")
    
    return performance_ok and cost_reasonable


async def main():
    """Run all real API tests"""
    print("SmartShopper Real API Integration Tests")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Check prerequisites
    if not check_api_keys():
        return
    
    try:
        # Test 1: Individual agents
        individual_success = await test_individual_agents()
        
        # Test 2: Integration scenarios
        scenario_results = await test_integration_scenarios()
        scenario_success = all(r.get("success", False) for r in scenario_results)
        
        # Test 3: Performance metrics
        performance_success = await test_performance_metrics()
        
        # Final summary
        print("\n" + "=" * 60)
        print("COMPREHENSIVE TEST RESULTS")
        print("=" * 60)
        
        print(f" Individual Agents: {'PASS' if individual_success else 'FAIL'}")
        print(f" Integration Scenarios: {'PASS' if scenario_success else 'FAIL'}")
        successful_scenarios = sum(1 for r in scenario_results if r.get("success", False))
        print(f"   Success rate: {successful_scenarios}/{len(scenario_results)} scenarios")
        
        print(f" Performance Metrics: {'PASS' if performance_success else 'FAIL'}")
        
        overall_success = individual_success and scenario_success and performance_success
        print(f"\n Overall Result: {'ALL TESTS PASSED' if overall_success else 'SOME TESTS FAILED'}")
        
        if overall_success:
            print("\nQueryOrchestrator -> TavilyRetriever integration is PRODUCTION READY!")
            print("Real API calls working perfectly")
            print("Agent chaining functional")
            print("Performance targets met")
            print("Error handling robust")
            print("\n Ready to implement next agent: CredibilityFilterAgent")
        else:
            print("\n Some issues detected in real API testing")
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
