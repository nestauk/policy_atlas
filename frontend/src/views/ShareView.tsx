import { useParams } from "react-router";

import { useProject } from "../api/queries";
import { useDocumentTitle } from "../lib/title";
import { COPY, LIFECYCLE_LABELS } from "../lib/vocabulary";
import { Card, PaneHeading } from "../ui/brand/Card";

/**
 * Share: named as missing rather than absent.
 *
 * The stage exists in the lifecycle because sharing is part of the work; it
 * says plainly that it cannot do it yet. An honest "not built" beats a tab
 * that quietly isn't there — the reader can tell the difference between a
 * feature that is coming and one that was never planned.
 */
export function ShareView() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  useDocumentTitle(project.data?.name, LIFECYCLE_LABELS.share);

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <PaneHeading>{LIFECYCLE_LABELS.share}</PaneHeading>
      <Card className="mt-4">
        <p className="text-body text-grey">{COPY.shareComingSoon}</p>
      </Card>
    </main>
  );
}
