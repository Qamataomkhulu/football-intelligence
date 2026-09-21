import Link from "next/link";
import { notFound } from "next/navigation";
import { getDashboardData, MarketPrice } from "../../../lib/data";

function fmtPct(n: number | null) {
  if (n === null) return "—";
  return `${Math.round(n * 100)}%`;
}

export default function FixturePage({ params }: { params: { id: string } }) {
  const data = getDashboardData();
  const fixture = data?.fixtures.find((f) => f.fixture_id === params.id);

  if (!data || !fixture) {
    notFound();
  }

  const sortedMarkets = [...fixture!.markets].sort((a, b) => (b.ratio ?? 0) - (a.ratio ?? 0));
  const bestMarket = sortedMarkets.find((m) => m.ratio !== null);

  return (
    <>
      <Link href="/" className="back-link">
        ← back to dashboard
      </Link>

      <div className="fixture-header">
        {fixture!.home_team} <span className="vs">vs</span> {fixture!.away_team}
      </div>
      <div className="mono" style={{ color: "var(--text-dim)", fontSize: 13 }}>
        expected goals {fixture!.expected_goals.home.toFixed(2)} – {fixture!.expected_goals.away.toFixed(2)}
      </div>

      <div className="rating-grid">
        <RatingCol title={fixture!.home_team} rating={fixture!.home_power_rating} />
        <RatingCol title={fixture!.away_team} rating={fixture!.away_power_rating} />
      </div>

      {bestMarket && (
        <section className="panel">
          <div className="panel-header">
            <div className="panel-title ticket-b">ENGINE CHOICE</div>
          </div>
          <div className="empty-note" style={{ color: "var(--text)" }}>
            <span className="mono" style={{ fontSize: 20, color: "var(--edge)" }}>
              {bestMarket.label}
            </span>
            <div style={{ marginTop: 8, color: "var(--text-dim)", fontSize: 13 }}>
              model {fmtPct(bestMarket.model_probability)} vs market {fmtPct(bestMarket.market_implied_probability)}{" "}
              — survival ratio {bestMarket.ratio?.toFixed(2)}x
            </div>
          </div>
        </section>
      )}

      <div className="reasons-risks">
        <div className="rr-col reasons">
          <h3>WHY</h3>
          <ul>
            {[...fixture!.reasons_home, ...fixture!.reasons_away].map((r, i) => (
              <li key={i}>{r}</li>
            ))}
            {fixture!.reasons_home.length === 0 && fixture!.reasons_away.length === 0 && (
              <li style={{ color: "var(--text-dim)" }}>No standout structural reasons recorded.</li>
            )}
          </ul>
        </div>
        <div className="rr-col risks">
          <h3>RISKS</h3>
          <ul>
            {fixture!.risks.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
            {fixture!.risks.length === 0 && <li style={{ color: "var(--text-dim)" }}>No elevated risks flagged.</li>}
          </ul>
        </div>
      </div>

      <section className="panel">
        <div className="panel-header">
          <div className="panel-title">MARKET OPTIONS</div>
          <div className="panel-sub">ranked by model / market ratio - the market survival engine</div>
        </div>
        <div className="markets-table-wrap">
          <table className="traps-table">
            <thead>
              <tr>
                <th>Market</th>
                <th style={{ textAlign: "right" }}>Model</th>
                <th style={{ textAlign: "right" }}>Market implied</th>
                <th style={{ textAlign: "right" }}>Ratio</th>
              </tr>
            </thead>
            <tbody>
              {sortedMarkets.map((m: MarketPrice) => (
                <tr key={m.market_code}>
                  <td className="mono">{m.label}</td>
                  <td className="mono" style={{ textAlign: "right" }}>
                    {fmtPct(m.model_probability)}
                  </td>
                  <td className="mono" style={{ textAlign: "right", color: "var(--text-dim)" }}>
                    {fmtPct(m.market_implied_probability)}
                  </td>
                  <td
                    className="mono"
                    style={{
                      textAlign: "right",
                      color: m.ratio && m.ratio >= 1.05 ? "var(--edge)" : "var(--text-dim)",
                    }}
                  >
                    {m.ratio ? `${m.ratio.toFixed(2)}x` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function RatingCol({
  title,
  rating,
}: {
  title: string;
  rating: { structural_pct: number; friction_pct: number; rating: number };
}) {
  return (
    <div className="rating-col">
      <h3>{title}</h3>
      <div className="rating-line">
        <span>Structural</span>
        <b>{rating.structural_pct.toFixed(0)}%</b>
      </div>
      <div className="rating-line">
        <span>Friction</span>
        <b>{rating.friction_pct.toFixed(0)}%</b>
      </div>
      <div className="rating-line">
        <span>Power rating</span>
        <b>{rating.rating.toFixed(0)}/100</b>
      </div>
    </div>
  );
}
