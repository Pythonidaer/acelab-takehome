import { useCallback, useMemo, useState } from "react";
import type { AgentReport, ProductRecommendation, StreamEvent } from "./types";

const DEFAULT_BRIEF =
  "High-traffic hospital corridor requiring infection control standards, LEED Silver minimum, calming aesthetic, and mid-range budget.";

const EXAMPLE_BRIEFS: { label: string; text: string }[] = [
  {
    label: "Healthcare Lobby",
    text: DEFAULT_BRIEF,
  },
  {
    label: "School Hallway",
    text: 'An architect likes Armstrong-style commercial flooring and wants comparable resilient flooring for a busy school hallway. Prioritize durable, easy-clean products from established manufacturers.',
  },
  {
    label: "Hospitality Flooring",
    text: "Large-format porcelain tile system for high-traffic commercial lobby flooring. Slip resistance, durability, and premium stone-like appearance.",
  },
  {
    label: "Multi-material Clinic",
    text: "Healthcare clinic reception: Caesarstone-style white quartz counters, Armstrong-style resilient flooring, large-format porcelain accent tile. Check duplicates for quartz, taxonomy, LEED-relevant certs.",
  },
];

type OrchestrationItem =
  | { type: "step"; id: string; label: string; at: number }
  | { type: "tool"; tool: string; label: string; summary: string; at: number };

async function streamRecommendation(
  prompt: string,
  trace: boolean,
  onEvent: (e: StreamEvent) => void,
): Promise<void> {
  const res = await fetch("/api/recommend/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, trace }),
  });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    for (;;) {
      const sep = buf.indexOf("\n\n");
      if (sep < 0) break;
      const block = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      for (const line of block.split("\n")) {
        if (line.startsWith("data: ")) {
          onEvent(JSON.parse(line.slice(6)) as StreamEvent);
        }
      }
    }
  }
}

function Mark({ className = "" }: { className?: string }) {
  return (
    <div
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[6px] bg-ink font-sans text-[15px] font-semibold leading-none tracking-tight text-cream shadow-sm ${className}`}
      aria-hidden
    >
      M
    </div>
  );
}

export default function App() {
  const [brief, setBrief] = useState(DEFAULT_BRIEF);
  const [showTrace, setShowTrace] = useState(false);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<AgentReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [orch, setOrch] = useState<OrchestrationItem[]>([]);
  const [traceLines, setTraceLines] = useState<string[]>([]);
  const [toolsUsed, setToolsUsed] = useState<string[]>([]);

  const resetForRun = useCallback(() => {
    setReport(null);
    setError(null);
    setOrch([]);
    setTraceLines([]);
    setToolsUsed([]);
  }, []);

  const run = useCallback(async () => {
    const prompt = brief.trim();
    if (!prompt) return;
    resetForRun();
    setLoading(true);
    const t0 = Date.now();
    const toolOrder: string[] = [];

    try {
      await streamRecommendation(prompt, showTrace, (ev) => {
        if (ev.kind === "step") {
          setOrch((o) => [...o, { type: "step", id: ev.id, label: ev.label, at: Date.now() - t0 }]);
        }
        if (ev.kind === "tool") {
          toolOrder.push(ev.label);
          setToolsUsed([...toolOrder]);
          setOrch((o) => [
            ...o,
            { type: "tool", tool: ev.tool, label: ev.label, summary: ev.summary, at: Date.now() - t0 },
          ]);
        }
        if (ev.kind === "trace") {
          setTraceLines((lines) => [...lines, ev.message]);
        }
        if (ev.kind === "complete") {
          setReport(ev.report);
          if (ev.trace !== undefined) {
            setTraceLines(ev.trace);
          }
        }
        if (ev.kind === "error") {
          setError(ev.message);
        }
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [brief, resetForRun, showTrace]);

  const uniqueTools = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const t of toolsUsed) {
      if (!seen.has(t)) {
        seen.add(t);
        out.push(t);
      }
    }
    return out;
  }, [toolsUsed]);

  const hasResults = report && !error;

  return (
    <div className="flex min-h-dvh flex-col overflow-y-auto bg-cream text-ink md:h-dvh md:max-h-dvh md:overflow-hidden">
      <header className="shrink-0 border-b border-ink/[0.06] bg-cream/95 px-6 py-6 backdrop-blur-sm sm:px-10 sm:py-7 md:px-12">
        <div className="mx-auto flex max-w-[1400px] flex-col gap-5 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
          <div className="flex min-w-0 items-center gap-4 sm:gap-5">
            <Mark className="!h-10 !w-10 !text-[1rem]" />
            <div className="min-w-0">
              <h1 className="font-serif text-[1.65rem] font-normal leading-[1.12] tracking-[-0.02em] text-ink sm:text-[1.85rem]">
                Material Recommendation Agent
              </h1>
              <p className="mt-1 max-w-[28rem] font-sans text-[13px] font-normal leading-snug text-subtle/90">
                AI-assisted architectural material search and recommendation system.
              </p>
            </div>
          </div>
          <p className="shrink-0 font-sans text-[10px] font-medium uppercase tracking-[0.22em] text-subtle/80 sm:pt-0.5">
            Acelab SDK · Demo
          </p>
        </div>
      </header>

      <div className="mx-auto flex min-h-0 w-full max-w-[1400px] flex-1 flex-col md:flex-row md:overflow-hidden">
        {/* Left: input workspace — solid, bordered column; scrolls only if needed */}
        <aside
          className="flex w-full shrink-0 flex-col overflow-y-auto border-ink/[0.05] bg-cream px-6 py-7 md:min-h-0 md:w-[392px] md:border-r md:py-9 sm:px-8"
          aria-label="Project input"
        >
          <div className="rounded-2xl border border-ink/[0.07] bg-white p-6 shadow-[0_1px_3px_rgba(26,24,22,0.05)] sm:p-7">
            <label className="block font-sans text-[10px] font-medium uppercase tracking-[0.18em] text-subtle">
              Project brief
            </label>
            <textarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              rows={8}
              disabled={loading}
              className="mt-3 w-full resize-y rounded-[10px] border border-ink/[0.09] bg-white px-4 py-3 font-sans text-sm leading-relaxed text-ink outline-none ring-0 placeholder:text-subtle/70 focus:border-ink/20 focus:ring-2 focus:ring-ink/5"
              placeholder="Describe the space, performance needs, certifications, and aesthetic…"
            />

            <p className="mt-6 font-sans text-[10px] font-medium uppercase tracking-[0.18em] text-subtle">
              Example briefs
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLE_BRIEFS.map((ex) => (
                <button
                  key={ex.label}
                  type="button"
                  disabled={loading}
                  onClick={() => setBrief(ex.text)}
                  className="rounded-full border border-ink/[0.08] bg-white px-3 py-1.5 font-sans text-xs text-ink shadow-sm transition hover:border-ink/15 hover:bg-cream-deep disabled:opacity-50"
                >
                  {ex.label}
                </button>
              ))}
            </div>

            <label className="mt-8 flex cursor-pointer items-center gap-2 font-sans text-xs text-subtle">
              <input
                type="checkbox"
                checked={showTrace}
                disabled={loading}
                onChange={(e) => setShowTrace(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-ink/25 text-ink"
              />
              Show agent trace
            </label>

            <button
              type="button"
              disabled={loading || !brief.trim()}
              onClick={() => void run()}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl border border-ink/10 bg-cream-deep px-4 py-3.5 font-sans text-sm font-medium text-ink transition hover:border-ink/15 hover:bg-[#dfd9cc] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {loading ? "Generating…" : "Generate recommendations"}
              {!loading && <span aria-hidden>→</span>}
            </button>
          </div>
        </aside>

        {/* Right: results workspace — own scroll, solid ground */}
        <main
          className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-cream px-6 py-7 md:py-9 sm:px-10"
          aria-label="Recommendations"
        >
          <div className="mx-auto max-w-3xl">
            {!loading && !hasResults && !error && (
              <div className="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-dashed border-ink/[0.1] bg-white px-8 py-16 text-center shadow-[inset_0_1px_0_rgba(26,24,22,0.03)] md:min-h-[420px]">
                <Mark className="!mb-5 !h-12 !w-12 !rounded-lg !text-lg" />
                <h2 className="font-serif text-xl font-normal tracking-[-0.02em] text-ink">Awaiting your brief</h2>
                <p className="mt-3 max-w-md font-sans text-sm leading-relaxed text-subtle">
                  Describe your project on the left. The agent will decompose it into focused Acelab SDK calls
                  and return grounded material recommendations.
                </p>
              </div>
            )}

            {loading && (
              <div className="space-y-5 rounded-2xl border border-ink/[0.07] bg-white p-6 shadow-[0_1px_3px_rgba(26,24,22,0.05)] sm:p-7">
                <div className="space-y-3">
                  <div className="h-4 w-1/3 rounded bg-ink/[0.08]" />
                  <div className="h-3 w-full rounded bg-ink/[0.06]" />
                  <div className="h-3 w-5/6 rounded bg-ink/[0.06]" />
                </div>
                <OrchestrationList items={orch} active />
                <p className="font-sans text-xs text-subtle">
                  Multiple tool calls run against the live catalog. Recommendations are validated against product
                  search results.
                </p>
              </div>
            )}

            {error && (
              <div className="rounded-2xl border border-red-200/80 bg-red-50/90 px-6 py-5 shadow-[0_1px_2px_rgba(26,24,22,0.04)]">
                <p className="font-sans text-sm font-medium text-red-950">Something went wrong</p>
                <p className="mt-2 font-mono text-xs leading-relaxed text-red-900/90">{error}</p>
              </div>
            )}

            {hasResults && report && (
              <div className="space-y-6 pb-6">
                <div className="rounded-2xl border border-ink/[0.07] bg-white p-6 shadow-[0_1px_3px_rgba(26,24,22,0.05)] sm:p-7">
                  <h2 className="font-serif text-lg font-normal tracking-[-0.02em] text-ink">Summary</h2>
                  <p className="mt-2.5 font-sans text-sm leading-relaxed text-subtle">{report.executive_summary}</p>

                  <StrategyBlock
                    constraints={report.key_constraints}
                    tools={uniqueTools}
                    strategy={report.search_strategy}
                  />

                  <h3 className="mt-6 font-serif text-base font-normal tracking-[-0.02em] text-ink">Recommendations</h3>
                  <p className="mt-1 font-sans text-xs text-subtle">
                    Ranked options from catalog search; identifiers match grounded{" "}
                    <code className="rounded bg-cream-deep px-1 font-mono text-[11px] text-ink">search_products</code>{" "}
                    results.
                  </p>
                  <ul className="mt-4 list-none space-y-3 p-0">
                    {report.recommendations.map((r) => (
                      <li key={`${r.product_id}-${r.rank}`}>
                        <RecommendationCard rec={r} />
                      </li>
                    ))}
                  </ul>

                  {report.caveats.length > 0 && (
                    <div className="mt-6 border-t border-ink/10 pt-5">
                      <p className="font-sans text-[10px] font-medium uppercase tracking-[0.18em] text-subtle">
                        Caveats
                      </p>
                      <ul className="mt-2 list-inside list-disc space-y-1 font-sans text-sm text-subtle">
                        {report.caveats.map((c, i) => (
                          <li key={i} className="leading-relaxed">
                            {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {showTrace && traceLines.length > 0 && (
                  <div className="rounded-xl border border-ink/10 bg-[#1a1917] p-5 text-cream-muted">
                    <p className="font-sans text-[10px] font-medium uppercase tracking-[0.2em] text-[#9c958c]">
                      Agent trace
                    </p>
                    <pre className="mt-3 max-h-72 overflow-auto rounded border border-[#2c2a28] bg-[#141312] p-3 font-mono text-[11px] leading-relaxed text-[#e8e4dc]">
                      {traceLines.join("\n")}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

function OrchestrationList({ items, active }: { items: OrchestrationItem[]; active?: boolean }) {
  if (items.length === 0) {
    return (
      <ul className="space-y-2 font-sans text-xs text-subtle">
        <li className="flex items-center gap-2 text-subtle">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-ink/35" />
          Analyzing brief…
        </li>
      </ul>
    );
  }
  const tail = items.slice(-12);
  return (
    <ul className="space-y-2.5">
      {tail.map((it, idx) => {
        const isLast = idx === tail.length - 1;
        return (
          <li
            key={`${it.type}-${it.at}-${idx}`}
            className="flex gap-3 font-sans text-xs text-ink"
          >
            <span
              className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                isLast && active ? "bg-ink" : "bg-ink/35"
              }`}
            />
            <div>
              <span className="font-medium">{it.label}</span>
              {it.type === "tool" && (
                <p className="mt-0.5 text-[11px] leading-snug text-subtle">{it.summary}</p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function StrategyBlock(props: { constraints: string[]; tools: string[]; strategy: string }) {
  return (
    <section className="mt-5 border-t border-ink/[0.07] pt-5" aria-labelledby="search-strategy-heading">
      <p
        id="search-strategy-heading"
        className="font-sans text-[10px] font-medium uppercase tracking-[0.18em] text-subtle"
      >
        Search strategy
      </p>
      <p className="mt-2 max-w-none font-sans text-sm leading-relaxed text-ink">{props.strategy}</p>

      <p className="mt-4 font-sans text-[10px] font-medium uppercase tracking-[0.18em] text-subtle">
        Identified constraints
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {props.constraints.map((c) => (
          <span
            key={c}
            className="rounded border border-ink/10 bg-white px-2 py-0.5 font-sans text-[11px] leading-snug text-ink"
          >
            {c}
          </span>
        ))}
      </div>

      <p className="mt-4 font-sans text-[10px] font-medium uppercase tracking-[0.18em] text-subtle">
        Tools used (SDK)
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {props.tools.length === 0 ? (
          <span className="font-sans text-xs italic text-subtle">—</span>
        ) : (
          props.tools.map((t) => (
            <span
              key={t}
              className="rounded border border-ink/10 bg-white px-2 py-0.5 font-mono text-[10px] leading-snug text-ink"
            >
              {t}
            </span>
          ))
        )}
      </div>
    </section>
  );
}

function RecommendationCard({ rec }: { rec: ProductRecommendation }) {
  const score =
    rec.similarity_score != null ? (rec.similarity_score * 100).toFixed(1) + "% match" : "—";
  const idDisplay = `${rec.product_id.slice(0, 8)}…`;

  const copyId = () => {
    void navigator.clipboard?.writeText(rec.product_id).catch(() => {});
  };

  return (
    <article className="rounded-[14px] border border-ink/[0.08] bg-white px-4 py-4 shadow-[0_1px_2px_rgba(26,24,22,0.04)]">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <h4 className="min-w-0 max-w-[min(100%,36rem)] font-serif text-[1.0625rem] leading-snug tracking-tight text-ink">
          <span className="mr-1.5 inline font-sans text-xs font-medium tabular-nums text-subtle">{rec.rank}.</span>
          {rec.product_name}
        </h4>
        <span className="shrink-0 pt-0.5 font-mono text-[11px] tabular-nums text-subtle">{score}</span>
      </div>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 font-sans text-xs text-subtle">
        <span className="text-ink/80">{rec.supplier ?? "Supplier unknown"}</span>
        <span className="hidden text-ink/25 sm:inline" aria-hidden>
          ·
        </span>
        <span
          title={rec.product_id}
          className="font-mono text-[10px] leading-none tracking-tight text-subtle tabular-nums"
        >
          {idDisplay}
        </span>
        <button
          type="button"
          onClick={copyId}
          aria-label={`Copy full product ID ${rec.product_id}`}
          className="ml-0 font-sans text-[10px] font-normal text-subtle underline decoration-subtle/40 underline-offset-2 transition hover:text-ink hover:decoration-ink/30"
        >
          Copy ID
        </button>
      </div>

      <p className="mt-2.5 border-t border-ink/[0.06] pt-2.5 font-sans text-sm leading-relaxed text-ink/90">
        {rec.reasoning}
      </p>

      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {rec.addresses.map((a) => (
          <span
            key={a}
            className="rounded border border-ink/10 bg-cream px-1.5 py-0.5 font-sans text-[10px] leading-tight text-subtle"
          >
            {a}
          </span>
        ))}
      </div>
    </article>
  );
}
