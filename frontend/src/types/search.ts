export interface SearchRequestPayload {
  query: string;
  max_results?: number;
  price_min?: number;
  price_max?: number;
  categories?: string[];
}

export interface ProductResult {
  title: string;
  brand?: string;
  price?: number;
  currency?: string;
  url?: string;
  domain?: string;
  specs: Record<string, unknown>;
  final_score: number;
  explanation?: string;
  credibility_score: number;
}

export interface AgentStepResult {
  agent_name: string;
  status: string;
  execution_time_ms: number;
  items_processed: number;
  cost_usd: number;
  error_message?: string | null;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface ExecutionMetrics {
  total_time_ms: number;
  agent_steps: AgentStepResult[];
  total_cost_usd: number;
  coverage_score: number;
}

export interface SearchResponse {
  run_id: string;
  query: string;
  intent?: string | null;
  results: ProductResult[];
  results_count: number;
  execution_metrics: ExecutionMetrics;
  errors: string[];
  warnings: string[];
}
