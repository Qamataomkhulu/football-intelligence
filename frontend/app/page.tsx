import Link from "next/link";
import { getDashboardData, TicketSelection } from "../lib/data";

function fmtPct(n: number) {
  return `${Math.round(n * 100)}%`;
}

function GapCell({ pp }: { pp: number }) {
  const cls = pp >= 0 ? "pos" : "neg";
  const sign = pp >= 0 ? "+" : "";
  return <span className={`selection-gap ${cls}`}>{sign}{pp.toFixed(1)}pp</span>;
}

function SelectionRow({ s }: { s: TicketSelection }) {
  return (
    <Link href={`/fixtures/${s.fixture_id}`} className="selection-row">
      <div className="selection-match">{s.match}</div>
      <div className="selection-market">{s.label}</div>
      <div className="mono" style={{ textAlign: "right", color: "var(--text-dim)" }}>
        model {fmtPct(s.model_probability)}
      </div>
      <GapCell pp={s.consensus_gap_pp} />
      <div className="selection-trap">{s.trap_score.toFixed(0)}/100</div>
    </Link>
  );
}

function TicketPanel({
  title,
  subtitle,
  accentClass,
  selections,
  targetOdds,
  emptyNote,
}: {
  title: string;
  subtitle: string;
  accentClass: string;
  selections: TicketSelection[];
  targetOdds: number | null;
  emptyNote: string;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <div className={`panel-title ${accentClass}`}>{title}</div>
          <div className="panel-sub">{subtitle}</div>
        </div>
        {targetOdds ? (
          <div className="target-odds">
            target <b>{targetOdds.toFixed(1)}x</b>
          </div>
        ) : null}
      </div>
      {selections.length === 0 ? (
        <div className="empty-note">{emptyNote}</div>
      ) : (
        selections.map((s) => <SelectionRow key={`${s.fixture_id}-${s.market_code}`} s={s} />)
      )}
    </section>
  );
}

export default function DashboardPage() {
  const data = getDashboardData();

  if (!data) {
    return (
      <div className="panel">
        <div className="empty-note">
          No pipeline output yet. Run <span className="mono">python scripts/run_pipeline.py</span>{" "}
          from the repo root to generate <span className="mono">data/predictions/latest.json</span>,
          then reload this page.
        </div>
      </div>
    );
  }

  const { summary, tickets, fixtures, generated_at } = data;

  const traps = [...tickets.ticket_b.selections]
    .sort((a, b) => Math.abs(b.consensus_gap_pp) - Math.abs(a.consensus_gap_pp))
    .slice(0, 5);

  return (
    <>
      <div className="timestamp" style={{ marginBottom: 16 }}>
        Last run: {new Date(generated_at).toUTCString()}
      </div>

      <div className="summary-strip">
        <div className="summary-cell">
          <div className="num mono">{summary.matches_scanned}</div>
          <div className="label">matches scanned</div>
        </div>
        <div className="summary-cell">
          <div className="num mono">{summary.matches_analysed}</div>
          <div className="label">matches analysed</div>
        </div>
        <div className="summary-cell">
          <div className="num mono" style={{ color: "var(--ticket-a)" }}>
            {summary.ticket_a_count}
          </div>
          <div className="label">structural value picks</div>
        </div>
        <div className="summary-cell">
          <div className="num mono" style={{ color: "var(--ticket-b)" }}>
            {summary.ticket_b_count}
          </div>
          <div className="label">consensus breakers</div>
        </div>
      </div>

      <TicketPanel
        title="TICKET A — STRUCTURAL VALUE"
        subtitle="Strongest evidence-to-risk relationship"
        accentClass="ticket-a"
        selections={tickets.ticket_a.selections}
        targetOdds={tickets.ticket_a.target_odds}
        emptyNote="No fixture cleared the Ticket A consensus threshold today - the market and the model are broadly in agreement across today's scanned fixtures."
      />

      <TicketPanel
        title="TICKET B — CONSENSUS BREAKER"
        subtitle="Where the market is most likely wrong, and the market that best expresses it"
        accentClass="ticket-b"
        selections={tickets.ticket_b.selections}
        targetOdds={tickets.ticket_b.target_odds}
        emptyNote="No fixture produced a surviving consensus gap today."
      />

      {traps.length > 0 && (
        <section className="panel">
          <div className="panel-header">
            <div className="panel-title">TOP MARKET TRAPS</div>
          </div>
          <div className="markets-table-wrap">
            <table className="traps-table">
              <thead>
                <tr>
                  <th>Match</th>
                  <th>Market says</th>
                  <th>Model says</th>
                  <th style={{ textAlign: "right" }}>Edge</th>
                </tr>
              </thead>
              <tbody>
                {traps.map((t) => (
                  <tr key={t.fixture_id}>
                    <td>
                      <Link href={`/fixtures/${t.fixture_id}`}>{t.match}</Link>
                    </td>
                    <td className="mono">
                      {t.market_implied_probability !== null
                        ? fmtPct(t.market_implied_probability)
                        : "—"}{" "}
                      implied
                    </td>
                    <td className="mono">
                      {t.label} <span style={{ color: "var(--text-dim)" }}>({fmtPct(t.model_probability)})</span>
                    </td>
                    <td className="mono" style={{ textAlign: "right", color: "var(--edge)" }}>
                      +{Math.abs(t.consensus_gap_pp).toFixed(1)}pp
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-header">
          <div className="panel-title">ALL ANALYSED FIXTURES</div>
          <div className="panel-sub">{fixtures.length} fixtures</div>
        </div>
        {fixtures.map((f) => (
          <Link key={f.fixture_id} href={`/fixtures/${f.fixture_id}`} className="selection-row">
            <div className="selection-match">
              {f.home_team} <span style={{ color: "var(--text-faint)" }}>vs</span> {f.away_team}
            </div>
            <div className="selection-market mono">
              xG {f.expected_goals.home.toFixed(2)}–{f.expected_goals.away.toFixed(2)}
            </div>
            <div className="mono" style={{ textAlign: "right", color: "var(--text-dim)" }}>
              rating {f.home_power_rating.rating.toFixed(0)}
            </div>
            <div className="mono" style={{ textAlign: "right", color: "var(--text-dim)" }}>
              rating {f.away_power_rating.rating.toFixed(0)}
            </div>
            <div className="pill">view →</div>
          </Link>
        ))}
      </section>
    </>
  );
}
