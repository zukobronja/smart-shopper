#!/usr/bin/env python3
"""
Export LangSmith logs for SmartShopper project to analyze Tavily credit usage.
Usage: python scripts/export_langsmith_logs.py
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Add backend to Python path
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

try:
    from langsmith import Client
    print("LangSmith client imported successfully")
except ImportError:
    print("LangSmith not installed. Run: pip install langsmith")
    sys.exit(1)


def export_langsmith_logs(
    project_name: str = None,
    output_file: str = "langsmith_logs.txt",
    days_back: int = 7,
    limit: Optional[int] = 100
):
    """
    Export LangSmith logs to analyze Tavily API usage and costs.
    
    Args:
        project_name: LangSmith project name
        output_file: Output file name
        days_back: Number of days to look back
        limit: Maximum number of runs to fetch (None for all)
    """
    try:
        # Initialize LangSmith client
        client = Client()
        print(f"Connecting to LangSmith project: {project_name}")
        
        # Calculate date range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        print(f"Fetching logs from {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
        
        # Fetch runs with filters
        runs = list(client.list_runs(
            project_name=project_name,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        ))
        
        print(f"Found {len(runs)} runs")
        
        # Export to file
        scripts_dir = Path(__file__).parent
        output_path = scripts_dir / output_file
        
        with open(output_path, "w", encoding="utf-8") as f:
            # Write header
            f.write(f"SmartShopper LangSmith Logs Export\n")
            f.write(f"Project: {project_name}\n")
            f.write(f"Period: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}\n")
            f.write(f"Total Runs: {len(runs)}\n")
            f.write("=" * 80 + "\n\n")
            
            tavily_cost_total = 0.0
            openai_cost_total = 0.0
            
            for i, run in enumerate(runs, 1):
                f.write(f"RUN #{i}\n")
                f.write(f"Run ID: {run.id}\n")
                f.write(f"Name: {run.name}\n")
                f.write(f"Status: {run.status}\n")
                f.write(f"Start Time: {run.start_time}\n")
                f.write(f"End Time: {run.end_time}\n")
                
                # Duration
                if run.start_time and run.end_time:
                    duration = (run.end_time - run.start_time).total_seconds()
                    f.write(f"Duration: {duration:.2f} seconds\n")
                
                # Inputs
                f.write(f"Inputs: {run.inputs}\n")
                
                # Outputs with cost analysis
                f.write(f"Outputs: {run.outputs}\n")
                
                # Error analysis
                if run.error:
                    f.write(f"ERROR: Error: {run.error}\n")
                
                # Cost analysis
                if hasattr(run, 'total_cost') and run.total_cost:
                    f.write(f"COST: Total Cost: ${run.total_cost:.4f}\n")
                
                # Extract Tavily usage from run metadata/tags
                if hasattr(run, 'extra') and run.extra:
                    extra = run.extra
                    if 'tavily_requests' in str(extra):
                        f.write(f"TAVILY: Contains Tavily API calls\n")
                    if 'openai_requests' in str(extra):
                        f.write(f"OPENAI: Contains OpenAI API calls\n")
                
                # Look for cost indicators in outputs
                if run.outputs:
                    output_str = str(run.outputs)
                    if 'tavily' in output_str.lower():
                        f.write(f"TAVILY: Run contains Tavily usage\n")
                    if 'cost' in output_str.lower():
                        # Try to extract cost info
                        import re
                        cost_matches = re.findall(r'\$?(\d+\.\d+)', output_str)
                        if cost_matches:
                            f.write(f"COST: Potential costs found: {cost_matches}\n")
                
                f.write("-" * 40 + "\n\n")
            
            # Summary
            f.write("\n" + "=" * 80 + "\n")
            f.write("SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"Total Runs Analyzed: {len(runs)}\n")
            f.write(f"Failed Runs: {sum(1 for r in runs if r.error)}\n")
            f.write(f"Successful Runs: {sum(1 for r in runs if not r.error)}\n")
            
            # Tavily usage analysis
            tavily_runs = [r for r in runs if 'tavily' in str(r.outputs).lower() or 'tavily' in str(r.inputs).lower()]
            f.write(f"Runs with Tavily usage: {len(tavily_runs)}\n")
            
            if tavily_cost_total > 0:
                f.write(f"Estimated Tavily costs: ${tavily_cost_total:.4f}\n")
            if openai_cost_total > 0:
                f.write(f"Estimated OpenAI costs: ${openai_cost_total:.4f}\n")
        
        print(f" Logs exported to: {output_path}")
        print(f"ANALYSIS: Analysis: {len(runs)} runs, {len([r for r in runs if 'tavily' in str(r.outputs).lower()])} with Tavily usage")
        
        return output_path
        
    except Exception as e:
        print(f"ERROR: Error exporting logs: {e}")
        return None


def main():
    """Main function with CLI arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Export LangSmith logs for SmartShopper")
    parser.add_argument("--project", default="SmartShopper-production", help="LangSmith project name")
    parser.add_argument("--output", default="langsmith_logs.txt", help="Output file name")
    parser.add_argument("--days", type=int, default=7, help="Days to look back")
    parser.add_argument("--limit", type=int, help="Max number of runs to fetch")
    
    args = parser.parse_args()
    
    # Check for environment variables
    langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
    if not langsmith_api_key:
        print("WARNING: LANGSMITH_API_KEY not found in environment")
        print("Make sure it's set in your .env file or export LANGSMITH_API_KEY=your_key_here")
        return
    
    print(f"Using LangSmith API key: {langsmith_api_key[:8]}...")
    
    # Set default project from environment if available
    default_project = os.getenv("LANGSMITH_PROJECT", args.project)
    if default_project != args.project:
        print(f"Using project from .env file: {default_project}")
        args.project = default_project
    
    # Run export
    output_path = export_langsmith_logs(
        project_name=args.project,
        output_file=args.output,
        days_back=args.days,
        limit=args.limit
    )
    
    if output_path:
        print(f"\nNEXT STEPS: Next steps:")
        print(f"1. Review the logs: cat {output_path}")
        print(f"2. Search for Tavily usage: grep -i tavily {output_path}")
        print(f"3. Look for cost patterns: grep -i cost {output_path}")


if __name__ == "__main__":
    main()