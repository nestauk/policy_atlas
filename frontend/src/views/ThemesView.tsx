import { Link, useParams } from "react-router";

import { useGroups, useLandscape, useProject } from "../api/queries";
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
 * Themes: the reader-facing landscape themes plus every grouping facet,
 * built only from existing read models (`landscape.themes`, `groups.facets`)
 * — no new text is generated here (rubric 25).
 */
export function ThemesView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  useDocumentTitle(project.data?.name, "Themes");
  const landscape = useLandscape(projectId);
  const groups = useGroups(projectId);

  // `not_found` is the server's honest shape for "no landscape/groups yet"
  // (screening hasn't run) — the expected empty state below, not a failure
  // to surface as an error, matching LandscapeView's own treatment.
  const landscapeErrorCode = landscape.isError ? errorCode(landscape.error) : null;
  const groupsErrorCode = groups.isError ? errorCode(groups.error) : null;
  const isUnauthenticated =
    landscapeErrorCode === "unauthenticated" || groupsErrorCode === "unauthenticated";
  const isError =
    (landscape.isError && landscapeErrorCode !== "not_found") ||
    (groups.isError && groupsErrorCode !== "not_found");
  const isPending = landscape.isPending || groups.isPending;

  const themes = orderThemes(landscape.data?.themes ?? []);
  const facets = (groups.data?.facets ?? []).filter((facet) => (facet.groups ?? []).length > 0);
  const isEmpty = !isPending && !isError && themes.length === 0 && facets.length === 0;

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
                void groups.refetch();
              }}
            >
              Retry
            </button>
          </Card>
        ))}

      {isEmpty && (
        <Card role="status" className="p-8 text-center text-body text-grey">
          Themes appear once screening has run.
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
                    ? `/projects/${projectId}/sources/all?theme=${theme.theme_id}`
                    : undefined
                }
              />
            ))}
          </ul>
        </section>
      )}

      {facets.map((facet) => (
        <section key={facet.facet} className="mt-8">
          <h2 className="text-meta font-extrabold uppercase tracking-[0.06em] text-grey">
            {scrub(facet.facet)}
          </h2>
          <ul role="list" className="mt-2">
            {(facet.groups ?? []).map((group) => (
              <ThemeRow
                key={group.label}
                name={group.label}
                size={group.size}
                description={group.description}
              />
            ))}
          </ul>
        </section>
      ))}
    </main>
  );
}
