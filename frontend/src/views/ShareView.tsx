import { Link, useParams } from "react-router";

import type { components } from "../api/gen/types";
import { useUpdateTask } from "../api/mutations";
import { useMe, useProjects, useTask } from "../api/queries";
import { conflictSentences, isConflictCode } from "../lib/errors";
import { useDocumentTitle } from "../lib/title";
import { LIFECYCLE_LABELS, PROJECT, PUBLIC_SHARE, TASK } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import { useToast } from "../ui/radix/Toast";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";
import { VisibilityControl, visibilityOutcomeLine } from "./VisibilityControl";

type Visibility = components["schemas"]["TaskOut"]["visibility"];

/**
 * Public link (task 037, contract § R1) — owner-only, mirrors the
 * `VisibilityControl` `isOwner` guard: the caller renders this only when
 * `task.data.is_owner`.
 */
function PublicLinkSection({
  isPublic,
  pending,
  onToggle,
  onCopyLink,
}: {
  isPublic: boolean;
  pending: boolean;
  onToggle: (next: boolean) => void;
  onCopyLink: () => void;
}) {
  return (
    <section aria-labelledby="public-link-heading" className="mt-8">
      <h2 id="public-link-heading" className="text-lead font-semibold text-navy">
        {PUBLIC_SHARE.heading}
      </h2>
      <p className="mt-2 text-body text-grey">
        {isPublic ? PUBLIC_SHARE.statusOn : PUBLIC_SHARE.statusOff}
      </p>
      <p className="mt-2 text-body text-grey">{PUBLIC_SHARE.warning}</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Button type="button" variant="ghost" disabled={pending} onClick={() => onToggle(!isPublic)}>
          {isPublic ? PUBLIC_SHARE.turnOff : PUBLIC_SHARE.turnOn}
        </Button>
        {isPublic && (
          <Button type="button" variant="ghost" onClick={onCopyLink}>
            {PUBLIC_SHARE.copyLink}
          </Button>
        )}
      </div>
    </section>
  );
}

/**
 * Share: assignment lives here from task creation. Real sharing/export is
 * still named as coming, not pretended to exist.
 */
export function ShareView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const projects = useProjects();
  const me = useMe();
  const update = useUpdateTask(taskId);
  const toast = useToast();
  useDocumentTitle(task.data?.name, LIFECYCLE_LABELS.share);

  // Visibility (task 033 phase 10b, moved here from the header popover):
  // hidden entirely without an organisation — sharing "with your
  // organisation" means nothing when there isn't one (rubric 14's
  // dark-launch invariant).
  const changeVisibility = (next: Visibility) => {
    update.mutate(
      { visibility: next },
      {
        onSuccess: () => toast.toast({ title: visibilityOutcomeLine(next), tone: "default" }),
        onError: (error) => {
          const code = (error as { code?: string }).code;
          toast.toast({
            title: isConflictCode(code)
              ? conflictSentences[code]
              : `The ${TASK.lower}'s visibility couldn't be changed. Try again.`,
            tone: "error",
          });
        },
      },
    );
  };

  const memberIds = task.data?.project_ids ?? [];
  const projectName = new Map(
    (projects.data?.data ?? []).map((project) => [project.project_id, project.name]),
  );
  const available = (projects.data?.data ?? []).filter(
    (project) => !memberIds.includes(project.project_id),
  );

  const setMembership = (projectIds: string[]) => {
    update.mutate({ project_ids: projectIds });
  };

  // Public link (task 037, contract § R1): owner-only, mirrors the
  // VisibilityControl `isOwner` guard below.
  const toggleIsPublic = (next: boolean) => {
    update.mutate(
      { is_public: next },
      {
        onSuccess: () =>
          toast.toast({
            title: next ? PUBLIC_SHARE.statusOn : PUBLIC_SHARE.statusOff,
            tone: "default",
          }),
        onError: () => toast.toast({ title: PUBLIC_SHARE.toggleFailed, tone: "error" }),
      },
    );
  };

  const copyPublicLink = () => {
    const url = `${window.location.origin}/tasks/${taskId}/result`;
    navigator.clipboard.writeText(url).then(
      () => toast.toast({ title: PUBLIC_SHARE.copied, tone: "default" }),
      () => toast.toast({ title: PUBLIC_SHARE.copyLink, description: url, tone: "error" }),
    );
  };

  return (
    <main className={`${LIFECYCLE_PAGE_CLASS} py-8`}>
      <Card className="p-6">
        <section aria-labelledby="membership-heading">
          <h2 id="membership-heading" className="text-lead font-semibold text-navy">
            {PROJECT.many} this {TASK.lower} belongs to
          </h2>
          {memberIds.length === 0 ? (
            <p className="mt-4 text-body text-grey">Not in a {PROJECT.lower} yet.</p>
          ) : (
            <ul className="mt-4 divide-y divide-line border-t border-line">
              {memberIds.map((projectId) => (
                <li key={projectId} className="flex items-center justify-between gap-3 py-3">
                  <Link
                    to={`/projects/${projectId}`}
                    className="text-body text-navy hover:text-blue hover:underline"
                  >
                    {projectName.get(projectId) ?? projectId}
                  </Link>
                  <Button
                    type="button"
                    variant="ghost"
                    className="text-body"
                    onClick={() =>
                      setMembership(memberIds.filter((candidate) => candidate !== projectId))
                    }
                    disabled={update.isPending}
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {available.length > 0 && (
            <label className="mt-6 block max-w-md">
              <span className="mb-2 block text-body font-semibold text-navy">
                Add to a {PROJECT.lower}
              </span>
              <select
                className="w-full border border-line-2 bg-paper px-3 py-2.5 text-body text-navy"
                defaultValue=""
                disabled={update.isPending}
                onChange={(event) => {
                  const value = event.target.value;
                  if (value === "") return;
                  setMembership([...memberIds, value]);
                  event.target.value = "";
                }}
              >
                <option value="">Select a {PROJECT.lower}</option>
                {available.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </section>
        {me.data?.organisation != null && task.data !== undefined && (
          <section aria-labelledby="visibility-heading" className="mt-8">
            <h2 id="visibility-heading" className="text-lead font-semibold text-navy">
              Organisation
            </h2>
            <p className="mt-2 text-body text-grey">
              {task.data.visibility === "private"
                ? "Private"
                : "Shared with your organisation"}
            </p>
            <VisibilityControl
              visibility={task.data.visibility}
              isOwner={task.data.is_owner}
              pending={update.isPending}
              onChange={changeVisibility}
              className="mt-2 px-0"
            />
          </section>
        )}
        {task.data !== undefined && task.data.is_owner && (
          <PublicLinkSection
            isPublic={task.data.is_public}
            pending={update.isPending}
            onToggle={toggleIsPublic}
            onCopyLink={copyPublicLink}
          />
        )}
      </Card>
    </main>
  );
}
