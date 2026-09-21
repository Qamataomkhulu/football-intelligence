import { getPerformanceData } from "../../lib/data";

export default function PerformancePage() {
  const perf = getPerformanceData();

  if (!perf || perf.n_settled === 0) {
    return (
      <div className="panel">
        <div className="empty-note">
          No settled predictions yet. Run <span className="mono">python scripts/settle_results.py</span>{" "}
          after results come in to populate this page.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">MODEL CALIBRATION</div>
          <div className="brier">
            {perf.n_settled} settled · Brier score <b style={{ color: "var(--text)" }}>{perf.brier_score}</b>
          </div>
        </div>
        <table className="calib-table">
          <thead>
            <tr>
              <th>Predicted bucket</th>
              <th style={{ textAlign: "right" }}>n</th>
              <th style={{ textAlign: "right" }}>Actual hit rate</th>
              <th style={{ textAlign: "right" }}>Calibration error</th>
            </tr>
          </thead>
          <tbody>
            {perf.calibration.map((b) => (
              <tr key={b.bucket}>
                <td>{b.bucket}</td>
                <td style={{ textAlign: "right" }}>{b.n}</td>
                <td style={{ textAlign: "right" }}>{Math.round(b.actual_hit_rate * 100)}%</td>
                <td
                  style={{
                    textAlign: "right",
                    color:
                      Math.abs(b.calibration_error) < 0.05
                        ? "var(--edge)"
                        : Math.abs(b.calibration_error) < 0.15
                        ? "var(--risk)"
                        : "var(--danger)",
                  }}
                >
                  {b.calibration_error >= 0 ? "+" : ""}
                  {Math.round(b.calibration_error * 100)}pp
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">HIT RATE BY MARKET</div>
        </div>
        <table className="calib-table">
          <thead>
            <tr>
              <th>Market</th>
              <th style={{ textAlign: "right" }}>n</th>
              <th style={{ textAlign: "right" }}>Wins</th>
              <th style={{ textAlign: "right" }}>Hit rate</th>
              <th style={{ textAlign: "right" }}>Avg model prob.</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(perf.hit_rate_by_market).map(([market, stats]) => (
              <tr key={market}>
                <td>{market}</td>
                <td style={{ textAlign: "right" }}>{stats.n}</td>
                <td style={{ textAlign: "right" }}>{stats.wins}</td>
                <td style={{ textAlign: "right" }}>{Math.round(stats.hit_rate * 100)}%</td>
                <td style={{ textAlign: "right", color: "var(--text-dim)" }}>
                  {Math.round(stats.avg_model_probability * 100)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {Object.keys(perf.loss_type_breakdown).length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">LOSS TYPE BREAKDOWN</div>
            <div className="panel-sub">what the engine gets wrong, classified</div>
          </div>
          <table className="calib-table">
            <thead>
              <tr>
                <th>Loss type</th>
                <th style={{ textAlign: "right" }}>Count</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(perf.loss_type_breakdown).map(([type, count]) => (
                <tr key={type}>
                  <td>{type.replaceAll("_", " ")}</td>
                  <td style={{ textAlign: "right" }}>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
