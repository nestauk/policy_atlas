import { useParams } from "react-router";

import { useGroups, useLandscape, useProject } from "../api/queries";
import { errorCode } from "../lib/errors";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Card, Divider, PaneHeading } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { orderThemes } from "../ui/charts/EvidenceDistributionChart";
import { ReauthRedirect } from "../ui/feedback";

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
    <main className="mx-auto max-w-5xl px-6 py-8">
      <h1 className="mb-1 font-display text-title font-extrabold text-navy">Themes</h1>
      <p className="mb-5 text-caption text-grey">
        The recurring themes and groups found across the screened-in sources.
      </p>

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
          <Card role="alert" className="p-8 text-center text-meta text-navy">
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
        <Card role="status" className="p-8 text-center text-meta text-grey">
          Themes appear once screening has run.
        </Card>
      )}

      {themes.length > 0 && (
        <Card>
          <PaneHeading>Key themes</PaneHeading>
          <Divider />
          <ul role="list" className="space-y-3 p-4">
            {themes.map((theme) => (
              <li key={theme.name} className="flex items-baseline gap-2.5">
                <Chip tone="blue">{theme.size}</Chip>
                <div>
                  <p className="text-body font-semibold text-navy">{scrub(theme.name)}</p>
                  <p className="text-body text-grey">{scrub(theme.description)}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {facets.map((facet) => (
        <Card key={facet.facet} className="mt-4">
          <PaneHeading>{scrub(facet.facet)}</PaneHeading>
          <Divider />
          <ul role="list" className="space-y-3 p-4">
            {(facet.groups ?? []).map((group) => (
              <li key={group.label} className="flex items-baseline gap-2.5">
                <Chip tone="soft">{group.size}</Chip>
                <div>
                  <p className="text-body font-semibold text-navy">{scrub(group.label)}</p>
                  <p className="text-body text-grey">{scrub(group.description)}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </main>
  );
}
