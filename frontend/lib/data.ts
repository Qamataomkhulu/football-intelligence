import fs from "fs";
import path from "path";

// Reads the pipeline's JSON output directly from the filesystem. This lets
// the dashboard work with `next dev` / `next build` with zero backend
// process running - the same data/predictions/latest.json that
// scripts/run_pipeline.py writes and backend/api/main.py serves over HTTP.
// Swap this for a `fetch(process.env.NEXT_PUBLIC_API_URL + "/api/dashboard")`
// call once the FastAPI backend is deployed separately.

const DATA_DIR = path.join(process.cwd(), "..", "data", "predictions");

export interface MarketPrice {
  market_code: string;
  label: string;
  model_probability: number;
  market_implied_probability: number | null;
  ratio: number | null;
}

export interface TicketSelection {
  fixture_id: string;
  match: string;
  ticket: "A" | "B";
  market_code: string;
  label: string;
  model_probability: number;
  market_implied_probability: number | null;
  edge_ratio: number | null;
  consensus_gap_pp: number;
  trap_score: number;
  reasons: string[];
  risks: string[];
  ticket_c: {
    ticket_b_market: string;
    ticket_c_market: string | null;
    reason: string;
  } | null;
}

export interface FixtureDetail {
  fixture_id: string;
  home_team: string;
  away_team: string;
  home_power_rating: { structural_pct: number; friction_pct: number; rating: number };
  away_power_rating: { structural_pct: number; friction_pct: number; rating: number };
  expected_goals: { home: number; away: number };
  markets: MarketPrice[];
  reasons_home: string[];
  reasons_away: string[];
  risks: string[];
}

export interface DashboardData {
  generated_at: string;
  summary: {
    matches_scanned: number;
    matches_analysed: number;
    ticket_a_count: number;
    ticket_b_count: number;
  };
  tickets: {
    ticket_a: { selections: TicketSelection[]; target_odds: number | null };
    ticket_b: { selections: TicketSelection[]; target_odds: number | null };
  };
  fixtures: FixtureDetail[];
}

export interface CalibrationBucket {
  bucket: string;
  n: number;
  predicted_midpoint: number;
  actual_hit_rate: number;
  calibration_error: number;
}

export interface PerformanceData {
  n_settled: number;
  calibration: CalibrationBucket[];
  brier_score: number | null;
  hit_rate_by_market: Record<string, { n: number; wins: number; hit_rate: number; avg_model_probability: number }>;
  loss_type_breakdown: Record<string, number>;
}

export function getDashboardData(): DashboardData | null {
  const file = path.join(DATA_DIR, "latest.json");
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

export function getPerformanceData(): PerformanceData | null {
  const file = path.join(DATA_DIR, "performance.json");
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}
