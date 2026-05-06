export interface ProductRecommendation {
  rank: number;
  product_id: string;
  product_name: string;
  supplier: string | null;
  similarity_score: number | null;
  reasoning: string;
  addresses: string[];
}

export interface AgentReport {
  executive_summary: string;
  key_constraints: string[];
  search_strategy: string;
  recommendations: ProductRecommendation[];
  caveats: string[];
}

export type StreamEvent =
  | { kind: "step"; id: string; label: string }
  | {
      kind: "tool";
      tool: string;
      label: string;
      args_preview: string;
      summary: string;
    }
  | { kind: "trace"; message: string }
  | { kind: "complete"; report: AgentReport; trace?: string[] }
  | { kind: "error"; message: string };
