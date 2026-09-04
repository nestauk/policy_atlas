/**
 * Splash feature steps (01–06). Hidden until product screenshots are ready —
 * flip {@link SHOW_SPLASH_FEATURE_STEPS} in SplashView to show again.
 */
export const SPLASH_FEATURES: {
  n: string;
  title: string;
  body: string;
  shot: string;
  flip?: boolean;
}[] = [
  {
    n: "01",
    title: "Quickly become an expert in a new topic",
    body: "Ask a question in plain language. Atlas plans the search, runs it, and comes back with a structured brief you can read in ten minutes.",
    shot: "Screenshot: report view",
  },
  {
    n: "02",
    title: "Collaborate on policy ideas",
    body: "Searches, plans and findings live in a shared space. Colleagues can pick up a run, question a source, and add what they know.",
    shot: "Screenshot: shared workspace",
    flip: true,
  },
  {
    n: "03",
    title: "Only uses trusted sources for evidence",
    body: "A named set of evidence libraries, journals and government publications. Every claim carries the citation it came from.",
    shot: "Screenshot: sources panel",
  },
  {
    n: "04",
    title: "Control AI-powered search and analysis",
    body: "You see the plan before it runs, edit any step, and watch the work as it happens. Nothing is decided out of sight.",
    shot: "Screenshot: plan approval",
    flip: true,
  },
  {
    n: "05",
    title: "Find evidence translatable to your domain",
    body: "Tell Atlas the setting you work in. Findings from adjacent fields and other countries come back with a note on how far they carry.",
    shot: "Screenshot: transferability note",
  },
  {
    n: "06",
    title: "Broaden the ideas to form and implement policy",
    body: "Move from what the evidence says to what you could do: options, trade-offs and the conditions each one depends on.",
    shot: "Screenshot: options compared",
    flip: true,
  },
];

/** Numbered feature grid between hero and Request access. */
export function SplashFeatureSteps() {
  return (
    <section className="flex justify-center border-t border-white/15 px-6">
      <div className="flex w-full max-w-[1180px] flex-col">
        {SPLASH_FEATURES.map((f) => (
          <div
            key={f.n}
            className="grid grid-cols-1 items-center gap-14 border-t border-white/15 py-[88px] first:border-t-0 md:grid-cols-2"
          >
            <div className={f.flip ? "md:order-2" : undefined}>
              <div className="text-body font-extrabold text-aqua">{f.n}</div>
              <h2 className="mt-3 max-w-[18em] font-display text-[clamp(28px,3vw,40px)] font-extrabold leading-[1.1] tracking-[-0.02em] text-pretty text-white">
                {f.title}
              </h2>
              <p className="mt-[18px] max-w-[30em] text-lead leading-[29px] text-navy-muted text-pretty">
                {f.body}
              </p>
            </div>
            <div
              className={`flex min-h-[280px] items-center justify-center border border-dashed border-white/30 bg-white/[0.04] text-body text-white/50 ${f.flip ? "md:order-1" : ""}`}
            >
              {f.shot}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
