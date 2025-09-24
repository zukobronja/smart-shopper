"""
QueryOrchestrator Agent for LangGraph Pipeline
Parses user queries into structured search parameters using OpenAI
"""
from typing import Dict, Any, List
from datetime import datetime
from app.agents.state import SmartShopperAgent, SmartShopperWorkflowState, SearchQuery, add_agent_step
from app.config import settings
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
import json

class QueryOrchestratorAgent(SmartShopperAgent):
    """
    Query Orchestrator Agent
    Parses user queries and determines search strategy
    """
    
    name = "Query Orchestrator"
    color = SmartShopperAgent.BLUE
    
    def __init__(self, llm_provider: str = "openai"):
        super().__init__()
        if llm_provider == "openai":
            self.llm = ChatOpenAI(
                model=settings.OPENAI_MODEL, 
                temperature=0, 
                api_key=settings.OPENAI_API_KEY
            )
            self.log("Initialized Query Orchestrator with llm_provider: OpenAI and model: " + settings.OPENAI_MODEL)
        else:
            # Placeholder for other LLM providers
            raise NotImplementedError("Only OpenAI is supported for now")
        
        self.prompt = self._create_prompt()

    def _create_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """You are a query parsing expert for an e-commerce search engine. Parse user queries into structured search parameters.

INSTRUCTIONS:
1. Extract search intent: "product_search", "review_search", or "comparison"
2. Identify product category, brand, budget constraints, and priorities
3. Create a normalized query for search engines
4. Output valid JSON only

SCHEMA:
{{
  "normalized_query": "cleaned search terms for search engines",
  "intent": "product_search|review_search|comparison", 
  "category": "laptop|smartphone|headphones|camera|tablet|monitor|etc",
  "brand": "apple|samsung|dell|hp|etc or null",
  "budget_min": number or null,
  "budget_max": number or null, 
  "constraints": ["under 2kg", "good battery life", "gaming", etc],
  "priorities": ["performance", "battery", "camera", "price", etc],
  "region": "US|EU|UK|etc"
}}

EXAMPLES:
Query: "gaming laptop under $2000 with good battery"
Output: {{"normalized_query": "gaming laptop", "intent": "product_search", "category": "laptop", "brand": null, "budget_min": null, "budget_max": 2000, "constraints": ["gaming", "good battery life"], "priorities": ["performance", "battery"], "region": "US"}}

Query: "iPhone 15 vs Samsung Galaxy S24 camera comparison"  
Output: {{"normalized_query": "iPhone 15 Samsung Galaxy S24 camera", "intent": "comparison", "category": "smartphone", "brand": null, "budget_min": null, "budget_max": null, "constraints": ["camera comparison"], "priorities": ["camera"], "region": "US"}}

Query: "best wireless headphones review 2024"
Output: {{"normalized_query": "wireless headphones 2024", "intent": "review_search", "category": "headphones", "brand": null, "budget_min": null, "budget_max": null, "constraints": ["wireless", "2024"], "priorities": [], "region": "US"}}

IMPORTANT: Return only valid JSON, no explanations."""),
            ("user", "Query: {query}"),
            ("assistant", "")
        ])

    def _generate_tavily_search_params(self, search_query: SearchQuery) -> Dict[str, Any]:
        """Generate search parameters for the Tavily API"""
        params = {
            "query": search_query.normalized_query,
            "search_depth": "advanced",
            "max_results": 10,
        }
        return params

    async def process(self, state: SmartShopperWorkflowState) -> SmartShopperWorkflowState:
        """
        Main processing method for LangGraph node
        Parses the user query and populates the search_query field in the state
        """
        self.log("Starting query parsing")
        
        start_time = datetime.now()
        
        try:
            raw_query = state.get("raw_query", "").strip()
            
            # Handle empty query gracefully
            if not raw_query:
                self.log("Empty query detected, using default values")
                search_query = SearchQuery(
                    raw_query="",
                    normalized_query="",
                    intent="product_search",
                    category=None,
                    brand=None,
                    budget_min=None,
                    budget_max=None,
                    constraints=[],
                    priorities=[],
                    region="US"
                )
                state["search_query"] = search_query
                
                # Minimal Tavily parameters for empty query
                state["tavily_search_params"] = {
                    "query": "",
                    "search_depth": "basic",
                    "max_results": 0
                }
                
                # Record execution
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                add_agent_step(
                    state,
                    self.name,
                    "success",
                    execution_time,
                    items_processed=1
                )
                
                return state
            
            self.log(f"Parsing query: '{raw_query}'")

            chain = self.prompt | self.llm | StrOutputParser()
            response = await chain.ainvoke({"query": raw_query})
            
            parsed_json = json.loads(response)
            
            search_query = SearchQuery(
                raw_query=raw_query,
                normalized_query=parsed_json.get("normalized_query", raw_query),
                intent=parsed_json.get("intent", "product_search"),
                category=parsed_json.get("category"),
                brand=parsed_json.get("brand"),
                budget_min=parsed_json.get("budget_min"),
                budget_max=parsed_json.get("budget_max"),
                constraints=parsed_json.get("constraints", []),
                priorities=parsed_json.get("priorities", []),
                region=parsed_json.get("region", "US")
            )
            
            state["search_query"] = search_query
            self.log(f"Successfully parsed query: {search_query.model_dump_json(indent=2)}")

            # Generate Tavily search parameters
            tavily_search_params = self._generate_tavily_search_params(search_query)
            # Store tavily params in a proper dict field (not directly in state)
            if "tavily_search_params" not in state:
                state["tavily_search_params"] = {}
            state["tavily_search_params"].update(tavily_search_params)
            self.log(f"Generated Tavily search params: {json.dumps(tavily_search_params, indent=2)}")
            
            # Record successful execution
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            add_agent_step(
                state, 
                self.name, 
                "success", 
                execution_time,
                items_processed=1,
                cost_usd=0.0  # OpenAI cost is minimal for query parsing
            )

        except Exception as e:
            self.log(f"Error in query parsing: {e}")
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Record failed execution
            add_agent_step(
                state, 
                self.name, 
                "error", 
                execution_time,
                error_message=str(e)
            )
            
            # Fallback to a simple SearchQuery object
            state["search_query"] = SearchQuery(
                raw_query=state.get("raw_query", ""), 
                normalized_query=state.get("raw_query", "")
            )
            if "tavily_search_params" not in state:
                state["tavily_search_params"] = {}
            state["tavily_search_params"]["query"] = state.get("raw_query", "")

        return state

def create_query_orchestrator_agent() -> QueryOrchestratorAgent:
    """Factory function to create the QueryOrchestratorAgent"""
    return QueryOrchestratorAgent()
