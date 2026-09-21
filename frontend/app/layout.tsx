import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "Match Intelligence",
  description: "An explainable football intelligence engine - not a tipster website.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <div className="topbar">
            <div className="brand">
              MATCH<span>_</span>INTELLIGENCE
            </div>
            <nav className="nav">
              <a href="/">Dashboard</a>
              <a href="/performance">Performance</a>
            </nav>
          </div>
          {children}
          <footer className="shell-footer">
            Deterministic scoring engine. Market selection is downstream of football
            analysis, never the reverse. LLM assistance is used only for narrative
            summaries - never for probabilities.
          </footer>
        </div>
      </body>
    </html>
  );
}
