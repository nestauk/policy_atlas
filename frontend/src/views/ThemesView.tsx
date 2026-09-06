import { Link, useParams } from "react-router";

import { useLandscape, useTask } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Card } from "../ui/brand/Card";
import { orderThemes } from "../ui/charts/EvidenceDistributionChart";
import { ReauthRedirect } from "../ui/feedback";

function documentCount(size: number): string {
  return size === 1 ? "1 document" : `${size} documents`;
}

function ThemeRow({
  name,
  size,
  description,
  to,
}: {
  name: string;
  size: number;
  description: string;
  to?: string;
}) {
  const body = (
    <>
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 text-lead font-bold text-navy">{scrub(name)}</p>
        <p className="shrink-0 text-body text-grey">{documentCount(size)}</p>
      </div>
      {description !== "" && <p className="mt-1 text-body text-grey">{scrub(description)}</p>}
    </>
  );
  return (
    <li className="border-b border-line last:border-b-0">
      {to !== undefined ? (
        <Link
          to={to}
          className="block py-4 no-underline hover:bg-paper-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
        >
          {body}
        </Link>
      ) : (
        <div className="py-4">{body}</div>
      )}
    </li>
  );
}

/**
 * Themes: the reader-facing landscape themes, built only from the existing
 * `landscape.themes` read model — no new text is generated here (rubric 25).
 * Finding-facet groups (intervention, barrier, …) live on the Findings tab.
 */
export function ThemesView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  useDocumentTitle(task.data?.name, "Themes");
  const landscape = useLandscape(taskId);

  // `not_found` is the server's honest shape for "no landscape yet"
  // (screening hasn't run) — the expected empty state below, not a failure
  // to surface as an error, matching LandscapeView's own treatment.
  const landscapeErrorCode = landscape.isError ? errorCode(landscape.error) : null;
  const isUnauthenticated = landscapeErrorCode === "unauthenticated";
  const isError = landscape.isError && landscapeErrorCode !== "not_found";
  const isPending = landscape.isPending;

  const themes = orderThemes(landscape.data?.themes ?? []);
  const isEmpty = !isPending && !isError && themes.length === 0;

  return (
    <main className="py-8">
      {isPending && (
        <div aria-busy="true" aria-label="Loading themes" className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {isError &&
        (isUnauthenticated ? (
          <ReauthRedirect />
        ) : (
          <Card role="alert" className="p-8 text-center text-body text-navy">
            Themes couldn't be loaded.{" "}
            <button
              type="button"
              className="cursor-pointer font-bold text-blue hover:underline"
              onClick={() => {
                void landscape.refetch();
              }}
            >
              Retry
            </button>
          </Card>
        ))}

      {isEmpty && (
        <Card role="status" className="p-8 text-center text-body text-grey">
          Themes appear once the Mapping step has finished.
        </Card>
      )}

      {themes.length > 0 && (
        <section>
          <ul role="list">
            {themes.map((theme) => (
              <ThemeRow
                key={theme.name}
                name={theme.name}
                size={theme.size}
                description={theme.description}
                to={
                  theme.theme_id
                    ? `/tasks/${taskId}/sources/all?theme=${theme.theme_id}`
                    : undefined
                }
              />
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
