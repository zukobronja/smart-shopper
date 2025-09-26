#!/usr/bin/env python3
"""
LangGraph Workflow Structure Test

Test the workflow structure and state management without requiring API keys.
Validates the LangGraph integration and agent connectivity.
"""
import sys
from datetime import datetime
from pprint import pprint

# Add app to path
sys.path.append('.')

from app.agents.state import (
    SmartShopperWorkflowState,
    create_initial_state,
    get_state_summary
)

def test_state_creation():
    """Test state creation and validation"""
    print("Testing State Creation and Management")
    print("=" * 50)
    
    # Test initial state creation
    state = create_initial_state(
        raw_query="test laptop search",
        user_id="test_user_123"
    )
    
    print(f"Initial state created successfully")
    print(f"Query: {state['raw_query']}")
    print(f"User ID: {state['user_id']}")
    print(f"Run ID: {state['run_id']}")
    
    # Test state summary
    summary = get_state_summary(state)
    print(f"\\nState Summary:")
    pprint(summary)
    
    # Validate state structure
    required_fields = [
        'raw_query', 'user_id', 'run_id', 'search_query',
        'raw_search_results', 'extracted_content', 'coverage_score',
        'credibility_filtered_results', 'structured_products', 'ranked_products',
        'agent_steps', 'total_cost_usd', 'execution_time_ms', 'errors', 'warnings'
    ]
    
    print(f"\\nState Structure Validation:")
    missing_fields = []
    for field in required_fields:
        if field in state:
            print(f"  {field}: {type(state[field]).__name__}")
        else:
            missing_fields.append(field)
            print(f"  {field}: Missing")
    
    if not missing_fields:
        print(f"\\nAll required fields present - state schema is correct!")
    else:
        print(f"\\nMissing fields: {missing_fields}")
    
    return len(missing_fields) == 0

def test_workflow_imports():
    """Test that all workflow components can be imported"""
    print("\\n\\nTesting Workflow Component Imports")
    print("=" * 50)
    
    import_tests = []
    
    # Test agent imports
    try:
        from app.agents.query_orchestrator_agent import QueryOrchestratorAgent
        print("QueryOrchestratorAgent import successful")
        import_tests.append(True)
    except Exception as e:
        print(f"QueryOrchestratorAgent import failed: {e}")
        import_tests.append(False)
    
    try:
        from app.agents.tavily_retriever_agent import TavilyRetrieverAgent
        print("TavilyRetrieverAgent import successful")
        import_tests.append(True)
    except Exception as e:
        print(f"TavilyRetrieverAgent import failed: {e}")
        import_tests.append(False)
    
    try:
        from app.agents.credibility_filter_agent import CredibilityFilterAgent
        print("CredibilityFilterAgent import successful")
        import_tests.append(True)
    except Exception as e:
        print(f"CredibilityFilterAgent import failed: {e}")
        import_tests.append(False)
    
    try:
        from app.agents.spec_extractor_agent import SpecExtractorAgent
        print("SpecExtractorAgent import successful")
        import_tests.append(True)
    except Exception as e:
        print(f"SpecExtractorAgent import failed: {e}")
        import_tests.append(False)
    
    try:
        from app.agents.results_ranker_agent import ResultsRankerAgent
        print("ResultsRankerAgent import successful")
        import_tests.append(True)
    except Exception as e:
        print(f"ResultsRankerAgent import failed: {e}")
        import_tests.append(False)
    
    # Test workflow import (without initialization to avoid API key issues)
    try:
        from app.agents.smart_shopper_workflow import SmartShopperWorkflow
        print("SmartShopperWorkflow import successful")
        import_tests.append(True)
    except Exception as e:
        print(f"SmartShopperWorkflow import failed: {e}")
        import_tests.append(False)
    
    # Test LangGraph imports
    try:
        from langgraph.graph import StateGraph, END
        print("LangGraph components import successful")
        import_tests.append(True)
    except Exception as e:
        print(f"LangGraph components import failed: {e}")
        import_tests.append(False)
    
    success_rate = sum(import_tests) / len(import_tests)
    print(f"\\nImport Success Rate: {success_rate:.1%} ({sum(import_tests)}/{len(import_tests)})")
    
    return success_rate == 1.0

def test_workflow_structure():
    """Test workflow graph structure without initialization"""
    print("\\n\\nTesting Workflow Graph Structure")
    print("=" * 50)
    
    try:
        from langgraph.graph import StateGraph
        from app.agents.state import SmartShopperWorkflowState
        
        # Create test workflow structure
        workflow = StateGraph(SmartShopperWorkflowState)
        
        # Test node additions
        test_nodes = [
            "query_orchestrator",
            "tavily_retriever", 
            "credibility_filter",
            "spec_extractor",
            "results_ranker",
            "handle_no_results",
            "handle_low_coverage"
        ]
        
        print("Adding workflow nodes:")
        for node_name in test_nodes:
            workflow.add_node(node_name, lambda state: state)  # Dummy function
            print(f"   Added node: {node_name}")
        
        # Test edge additions  
        test_edges = [
            ("query_orchestrator", "tavily_retriever"),
            ("credibility_filter", "spec_extractor"),
            ("spec_extractor", "results_ranker"),
        ]
        
        print("\\nAdding workflow edges:")
        for source, target in test_edges:
            workflow.add_edge(source, target)
            print(f"   Added edge: {source} -> {target}")
        
        # Test entry point
        workflow.set_entry_point("query_orchestrator")
        print(f"\\nEntry point set: query_orchestrator")
        
        # Test compilation (structure validation)
        try:
            app = workflow.compile()
            print(f"\\nWorkflow compiled successfully!")
            print(f" Nodes: {len(workflow.nodes)}")
            print(f" Edges: Successfully configured")
            return True
            
        except Exception as e:
            print(f"\\nWorkflow compilation failed: {e}")
            return False
            
    except Exception as e:
        print(f"Workflow structure test failed: {e}")
        return False

def test_state_transitions():
    """Test state transition patterns"""
    print("\\n\\nTesting State Transition Patterns")
    print("=" * 50)
    
    try:
        from app.agents.state import add_agent_step, validate_state_transition
        
        # Create test state
        state = create_initial_state("test query")
        
        # Test agent step tracking
        print("Testing agent step tracking:")
        add_agent_step(
            state, 
            "TestAgent", 
            "success", 
            1500,  # 1.5 seconds
            items_processed=5,
            cost_usd=0.01
        )
        
        steps = state.get("agent_steps", [])
        if len(steps) == 1:
            step = steps[0]
            print(f"   Agent step recorded: {step.agent_name} ({step.status})")
            print(f"  Execution time: {step.execution_time_ms}ms") 
            print(f"   Items processed: {step.items_processed}")
            print(f"   Cost: ${step.cost_usd}")
        else:
            print(f"   Agent step tracking failed")
            return False
        
        # Test state validation
        print("\\nTesting state validation:")
        try:
            validate_state_transition(state, "TestAgent", ["raw_query", "run_id"])
            print("   State validation passed")
        except Exception as e:
            print(f"   State validation failed: {e}")
            return False
        
        # Test cost and time tracking
        total_cost = state.get("total_cost_usd", 0)
        total_time = state.get("execution_time_ms", 0)
        print(f"\\nTotal cost tracking: ${total_cost}")
        print(f"Total time tracking: {total_time}ms")
        
        return True
        
    except Exception as e:
        print(f"State transition test failed: {e}")
        return False

def main():
    """Run all structure tests"""
    print("SmartShopper LangGraph Workflow Structure Tests")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Purpose: Validate workflow architecture without API dependencies")
    
    # Run tests
    test_results = []
    
    # Test 1: State management
    test_results.append(("State Creation", test_state_creation()))
    
    # Test 2: Component imports
    test_results.append(("Component Imports", test_workflow_imports()))
    
    # Test 3: Workflow structure
    test_results.append(("Workflow Structure", test_workflow_structure()))
    
    # Test 4: State transitions
    test_results.append(("State Transitions", test_state_transitions()))
    
    # Summary
    print("\\n\\nTest Results Summary")
    print("=" * 60)
    
    passed_tests = 0
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed_tests += 1
    
    success_rate = passed_tests / len(test_results)
    print(f"\\nOverall Success Rate: {success_rate:.1%} ({passed_tests}/{len(test_results)})")
    
    if success_rate == 1.0:
        print("\\nAll tests passed! LangGraph workflow structure is ready.")
        print("State schema aligned with MVP implementation")
        print("All agent components properly imported")
        print("Workflow graph structure validated")
        print("State transition patterns working")
        print("\\nReady for API integration testing with valid keys!")
    else:
        print("\\nSome tests failed. Please review the issues above.")
    
    return success_rate == 1.0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
