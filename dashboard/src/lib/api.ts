const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface KillShot {
  number: string;
  title: string;
  details: string;
}

export interface AgentOutput {
  role: string;
  content: string;
  kill_shots?: KillShot[];
  verdict?: string;
  citations?: string[];
  confidence?: number;
}

export interface DivergencePoint {
  topic: string;
  position_a: Record<string, unknown>;
  position_b: Record<string, unknown>;
  resolution_test: string;
}

export interface AnalysisResult {
  query: string;
  report: Record<string, unknown>;
  agent_outputs: AgentOutput[];
  divergence_points: DivergencePoint[];
  confidence_score: number;
  rounds: number;
}

export interface AnalysisSummary {
  analysis_id: string;
  query: string;
  timestamp: string;
  agent_count: number;
  divergence_count: number;
  confidence: number;
}

export interface DebateSummary {
  what_agents_agreed_on: string[];
  what_would_strengthen_the_idea: string[];
  key_disadvantages: string[];
}

export interface SWOTAnalysis {
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  threats: string[];
}

export interface CouncilAddendum {
  topic: string;
  insight: string;
  raised_by: string;
}

export interface AnalysisDetail {
  analysis_id: string;
  query: string;
  timestamp: string;
  market_analyst: AgentOutput | Record<string, unknown> | string;
  devils_advocate: AgentOutput | Record<string, unknown> | string;
  divergence_count: number;
  confidence: number;
  debate_summary?: DebateSummary;
  swot?: SWOTAnalysis;
  addendum?: CouncilAddendum | null;
}

export async function runAnalysis(idea: string, profile: string = "full"): Promise<AnalysisResult> {
  const res = await fetch(`${BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idea, profile }),
  });
  if (!res.ok) {
    throw new Error(`Analysis failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getHistory(limit = 20): Promise<{ analyses: AnalysisSummary[] }> {
  const res = await fetch(`${BASE}/api/history?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch history: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getAnalysis(id: string): Promise<AnalysisDetail> {
  const res = await fetch(`${BASE}/api/history/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch analysis: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

interface AgentLLMConfig {
  model: string;
  base_url: string | null;
  api_key: string | null;
  provider: string;
}

export interface AppSettings {
  market_analyst_model: string;
  market_analyst_base_url: string | null;
  market_analyst_api_key: string | null;
  market_analyst_provider: string;
  devils_advocate_model: string;
  devils_advocate_base_url: string | null;
  devils_advocate_api_key: string | null;
  devils_advocate_provider: string;
  divergence_model: string;
  divergence_base_url: string | null;
  divergence_api_key: string | null;
  divergence_provider: string;
  report_model: string;
  report_base_url: string | null;
  report_api_key: string | null;
  report_provider: string;
  enable_reddit: boolean;
  enable_hackernews: boolean;
  enable_crawl4ai: boolean;
  log_level: string;
}

export async function getSettings(): Promise<{ settings: AppSettings; timestamp: string }> {
  const res = await fetch(`${BASE}/api/settings`);
  if (!res.ok) throw new Error(`Failed to fetch settings: ${res.status}`);
  return res.json();
}

export async function updateSettings(update: Partial<AppSettings>): Promise<{ settings: AppSettings; updated_fields: string[] }> {
  const res = await fetch(`${BASE}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) throw new Error(`Failed to update settings: ${res.status}`);
  return res.json();
}

export async function testModelConnection(model: string, baseUrl?: string, apiKey?: string): Promise<{ success: boolean; response?: string; error?: string }> {
  const res = await fetch(`${BASE}/api/settings/test-model`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, base_url: baseUrl || null, api_key: apiKey || null }),
  });
  return res.json();
}
