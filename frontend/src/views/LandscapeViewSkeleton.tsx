import "./landscape.css";

/** Placeholder bar lengths (percent of the track), longest first. */
const SKELETON_BARS = [88, 64, 47, 31] as const;

/** The two sections a landscape always opens with. */
const SKELETON_SECTIONS = ["From search to citation", "Evidence types"] as const;

/**
 * The Landscape while its reads load (task 058, landscape polish): the
 * section frame with four rows of placeholder bars at the ranked-bar
 * geometry (14 px bars on a 30 px pitch), so the page does not jump when the
 * data arrives. The bars breathe on the status mark's rhythm and hold still
 * under reduced motion (`placeholder-bar`).
 *
 * No Recharts here: the route's Suspense fallback imports this module
 * without pulling the chart chunk.
 */
export function LandscapeSkeleton() {
  return (
    <div
      aria-busy="true"
      aria-label="Loading the landscape"
      data-testid="landscape-skeleton"
      className="mx-auto w-full max-w-3xl"
    >
      {SKELETON_SECTIONS.map((title) => (
        <section key={title} className="landscape-section" aria-hidden="true">
          <div className="border-b border-line pb-2.5 pt-3.5">
            <p className="text-meta font-extrabold uppercase tracking-[0.06em] text-grey">{title}</p>
          </div>
          <div className="ranked-bars pt-4">
            {SKELETON_BARS.map((length) => (
              <div key={length} className="ranked-bars__row">
                <span className="ranked-bars__label">
                  <span className="placeholder-bar h-2.5 w-28 max-w-full" />
                </span>
                <span className="ranked-bars__cell">
                  <span className="placeholder-bar ranked-bars__placeholder" style={{ width: `${length}%` }} />
                </span>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
