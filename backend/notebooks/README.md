# SmartShopper Development Notebooks

This directory contains Jupyter notebooks for interactive development and testing of SmartShopper components.

## 📚 Available Notebooks

### Phase 4: LangGraph Implementation 🔄
**File**: `multi_agent_rag_langgraph_implementation.ipynb`

**Purpose**: Interactive development and testing of the complete LangGraph pipeline for SmartShopper.

**Contents**:
- Step-by-step LangGraph pipeline implementation
- Interactive testing of each node (Orchestrator, Source Planner, Retrievers, etc.)
- Integration with Phase 3 extraction system
- Complete workflow testing and validation
- API integration examples

### Phase 4.1: Tavily Optimization ✅
**File**: `simple_tavily_test.ipynb`

**Purpose**: Comprehensive testing of the OptimizedTavilyClient with simplified setup and complete coverage.

**Contents**:
- **Basic Configuration**: Dev vs Production setup comparison
- **Query Optimization**: Multiple query types and intent testing
- **Coverage Analysis**: Realistic e-commerce content evaluation
- **API Integration**: All client methods (`search_step`, `extract_step`, `two_step_process`, etc.)
- **Domain Testing**: URL domain extraction validation
- **Performance Testing**: Speed and efficiency analysis
- **Error Handling**: Edge cases and robustness testing
- **Manual Testing**: Interactive experimentation area

**How to Use**:
1. Start Jupyter from the backend directory:
   ```bash
   cd backend
   jupyter lab
   ```
2. **For Tavily Testing**: Open `notebooks/simple_tavily_test.ipynb`
3. **For LangGraph Development**: Open `notebooks/multi_agent_rag_langgraph_implementation.ipynb`
4. Run cells sequentially to test components
5. Modify and experiment with different queries and configurations

## 🚀 Getting Started

### Prerequisites
- Python environment with SmartShopper dependencies
- Jupyter Lab installed (`uv add jupyter ipykernel --dev`)
- Optional: Tavily and OpenAI API keys for live testing

### Environment Setup
```bash
# From backend directory
uv add jupyter ipykernel langgraph langchain-openai --dev

# Start Jupyter Lab
jupyter lab
```

### API Keys (Optional)
For full functionality, set these environment variables:
```bash
export TAVILY_API_KEY="tvly-..."
export OPENAI_API_KEY="sk-..."
```

Without API keys, the notebooks will use mock data for testing.

## 📋 Development Workflow

1. **Interactive Development** - Use notebooks to prototype and test new features
2. **Validation** - Verify components work correctly with real data
3. **Integration Testing** - Test how components work together
4. **Code Extraction** - Move working code to production files
5. **Documentation** - Update documentation with findings

## 🔧 Features Demonstrated

### Phase 4 Pipeline
- **Query Orchestration** - Intelligent parsing and intent detection
- **Source Planning** - Hybrid search strategy (whitelist + discovery)
- **URL Retrieval** - Multi-source URL discovery
- **Credibility Filtering** - Quality assessment and filtering
- **Data Extraction** - Structured data extraction using Phase 3 system
- **Results Ranking** - Multi-criteria ranking and formatting

### Testing Capabilities
- **Component Isolation** - Test individual nodes
- **Integration Testing** - Full pipeline execution
- **Mock Data Support** - Test without API dependencies
- **Error Handling** - Graceful degradation testing
- **Performance Analysis** - Cost and speed optimization

## 📊 Example Queries for Testing

### For Tavily Testing (`simple_tavily_test.ipynb`)
```python
# Basic product searches
"gaming laptop RTX 4070 under $2000"
"best budget smartphone 2024"

# Comparison queries  
"iPhone 15 Pro vs Samsung Galaxy S24 Ultra camera"
"MacBook Air M2 vs M3 comparison"

# Review searches
"ergonomic office chair for back pain review"
"MacBook Pro M3 performance benchmarks"
```

### For LangGraph Pipeline Testing
```python
# Complete workflow queries
test_queries = [
    "gaming laptop under $1500",
    "best chef knife reviews", 
    "office chair for home workspace",
    "iPhone vs Samsung Galaxy comparison",
    "IKEA MARKUS office chair review"
]
```

## 🎯 Next Steps

After validating the pipeline in the notebook:
1. Extract working code to production files
2. Create proper module structure in `app/agents/`
3. Add comprehensive unit tests
4. Integrate with FastAPI endpoints
5. Deploy and monitor performance

## 💡 Tips for Development

- **Start Simple** - Test with basic queries first
- **Use Mock Data** - Don't waste API credits during development
- **Validate Each Step** - Check intermediate results
- **Document Findings** - Note what works and what doesn't
- **Cost Awareness** - Monitor API usage in live tests

## 🐛 Troubleshooting

**Import Errors**: Make sure you're running Jupyter from the backend directory and the Python path is correct.

**API Errors**: Check your API keys and rate limits. Use mock data for development.

**Memory Issues**: Restart the kernel if notebooks become slow or unresponsive.

**Environment Issues**: Ensure all dependencies are installed with `uv add jupyter ipykernel --dev`.

---

**Happy coding! 🚀**