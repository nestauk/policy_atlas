import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";

import type { components } from "../api/gen/types";
import { useUpdateTask } from "../api/mutations";
import { useMe, useProjects, useTask } from "../api/queries";
import { useDocumentTitle } from "../lib/title";
import { LIFECYCLE_LABELS } from "../lib/vocabulary";
import { Button, buttonVariants } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import { Select } from "../ui/brand/Select";
import { PROSE_LINK_CLASS } from "../ui/brand/inlineActions";
import { cn } from "../ui/brand/cn";
import { useToast } from "../ui/radix/Toast";
import { LIFECYCLE_PAGE_CLASS } from "./listPageChrome";
import { refusalSentence, SHARE_COPY } from "./sharePresentation";
import { visibilityOutcomeLine } from "./VisibilityControl";

type Visibility = components["schemas"]["TaskOut"]["visibility"];
type Section = "public" | "org" | "projects";

/** Every Share control is the outline button at 40 px (lead ruling S1, P1):
 *  access changes are settings, not progress, so nothing here carries the
 *  blue cut corner. */
const CONTROL_CLASS = "h-10 whitespace-nowrap py-0";

/** The 40 px outline control as classes, for the two buttons that take a ref. */
const OUTLINE_CONTROL_CLASS = cn(buttonVariants({ variant: "outline" }), CONTROL_CLASS);

/** How long "Copied" stays beside the button. */
const COPIED_MS = 2000;

/**
 * One settings row (S2): the heading and the current state on the left, the
 * control on the right; below `md` the control drops under the words. The
 * state is the answer the page exists to give, so it is Navy Semibold (S6);
 * a rule that explains it stays Grey.
 */
function SettingsRow({
  headingId,
  heading,
  state,
  note,
  control,
  children,
}: {
  headingId: string;
  heading: string;
  state?: string;
  note?: ReactNode;
  control?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section
      aria-labelledby={headingId}
      className="border-t border-line pt-6 mt-6 first:mt-0 first:border-t-0 first:pt-0"
    >
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-6 gap-y-3 max-md:grid-cols-1">
        <div className="min-w-0">
          <h2 id={headingId} className="text-lead font-semibold text-navy">
            {heading}
          </h2>
          {state !== undefined && <p className="mt-1 text-body font-semibold text-navy">{state}</p>}
          {note !== undefined && <p className="mt-1 text-body text-grey">{note}</p>}
        </div>
        {control !== undefined && <div className="flex flex-wrap gap-3">{control}</div>}
      </div>
      {children}
    </section>
  );
}

/** A refused or failed change, under the section it belongs to. */
function SectionError({ text }: { text: string | null }) {
  if (text === null) return null;
  return (
    <p role="alert" className="mt-3 text-body text-red">
      {text}
    </p>
  );
}

/**
 * Public link (task 037, contract § R1; round 10, S3): the owner makes the
 * task public in two steps, inline, and sees the link once it is public.
 */
function PublicLinkSection({
  taskId,
  isPublic,
  pending,
  error,
  onToggle,
}: {
  taskId: string;
  isPublic: boolean;
  pending: boolean;
  error: string | null;
  onToggle: (next: boolean, onDone: () => void) => void;
}) {
  const headingId = useId();
  const confirmId = useId();
  const [confirming, setConfirming] = useState(false);
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  const trigger = useRef<HTMLButtonElement>(null);
  const sentence = useRef<HTMLParagraphElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const copyButton = useRef<HTMLButtonElement>(null);
  const url = `${window.location.origin}/tasks/${taskId}/result`;

  // The confirm step takes focus on its sentence, so a screen reader hears
  // the consequence first and a second Enter does not publish.
  useEffect(() => {
    if (confirming) sentence.current?.focus();
  }, [confirming]);

  useEffect(() => {
    if (copy !== "copied") return undefined;
    const id = window.setTimeout(() => setCopy("idle"), COPIED_MS);
    return () => window.clearTimeout(id);
  }, [copy]);

  const cancel = () => {
    setConfirming(false);
    // The trigger is back once the step closes; return focus to it.
    window.setTimeout(() => trigger.current?.focus(), 0);
  };

  const copyLink = () => {
    const done = () => setCopy("copied");
    const failed = () => {
      setCopy("failed");
      field.current?.focus();
      field.current?.select();
    };
    if (navigator.clipboard?.writeText === undefined) {
      failed();
      return;
    }
    navigator.clipboard.writeText(url).then(done, failed);
  };

  return (
    <SettingsRow
      headingId={headingId}
      heading={SHARE_COPY.publicHeading}
      state={isPublic ? SHARE_COPY.publicOn : SHARE_COPY.publicOff}
      control={
        confirming ? undefined : (
          // The Button's own classes on a plain button, which takes a ref
          // for the focus to come back to.
          <button
            ref={trigger}
            type="button"
            className={OUTLINE_CONTROL_CLASS}
            disabled={pending}
            onClick={() => {
              if (isPublic) onToggle(false, () => setCopy("idle"));
              else setConfirming(true);
            }}
          >
            {isPublic ? SHARE_COPY.stopPublic : SHARE_COPY.makePublic}
          </button>
        )
      }
    >
      {confirming && !isPublic && (
        <div
          role="group"
          aria-labelledby={confirmId}
          className="mt-4"
          onKeyDown={(event) => {
            if (event.key === "Escape") cancel();
          }}
        >
          <p id={confirmId} ref={sentence} tabIndex={-1} className="text-body text-ink">
            {SHARE_COPY.confirmPublic}
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <Button
              variant="outline"
              className={CONTROL_CLASS}
              disabled={pending}
              onClick={() =>
                onToggle(true, () => {
                  setConfirming(false);
                  window.setTimeout(() => copyButton.current?.focus(), 0);
                })
              }
            >
              {SHARE_COPY.makePublic}
            </Button>
            <Button variant="ghost" className={cn(CONTROL_CLASS, "px-3")} disabled={pending} onClick={cancel}>
              {SHARE_COPY.keepPrivate}
            </Button>
          </div>
        </div>
      )}
      {isPublic && (
        <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
          <input
            ref={field}
            readOnly
            value={url}
            aria-label={SHARE_COPY.linkField}
            onFocus={(event) => event.currentTarget.select()}
            className="h-10 min-w-0 flex-1 basis-64 border border-line-2 bg-paper px-3 text-body text-ink"
          />
          <button ref={copyButton} type="button" className={OUTLINE_CONTROL_CLASS} onClick={copyLink}>
            {SHARE_COPY.copyLink}
          </button>
          {/* "Copied" has a slot of its own beside the button, so the field
              does not narrow when it appears; a failed copy says so on the
              line under the field it has selected (S4). */}
          <span
            aria-live="polite"
            className={cn("text-meta text-grey", copy === "failed" ? "basis-full" : "w-16 shrink-0")}
          >
            {copy === "copied" ? SHARE_COPY.copied : copy === "failed" ? SHARE_COPY.copyFailed : ""}
          </span>
        </div>
      )}
      <SectionError text={error} />
    </SettingsRow>
  );
}

/**
 * Share: who can read this task (a public link, the organisation) and which
 * projects it is filed under, in that order of consequence (round 10, S2).
 * The owner changes them; a colleague sees the state without the controls
 * the server would refuse them (S5, S8).
 */
export function ShareView() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const projects = useProjects();
  const me = useMe();
  const update = useUpdateTask(taskId);
  const toast = useToast();
  const titleId = useId();
  const orgHeadingId = useId();
  const projectsHeadingId = useId();
  const [error, setError] = useState<{ section: Section; text: string } | null>(null);
  useDocumentTitle(task.data?.name, LIFECYCLE_LABELS.share);

  const errorFor = (section: Section) => (error?.section === section ? error.text : null);
  const isOwner = task.data?.is_owner === true;
  const memberIds = task.data?.project_ids ?? [];
  const inProject = memberIds.length > 0;
  const projectName = new Map(
    (projects.data?.data ?? []).map((project) => [project.project_id, project.name]),
  );
  const available = (projects.data?.data ?? []).filter(
    (project) => !memberIds.includes(project.project_id),
  );

  // Visibility (task 033 phase 10b): hidden entirely without an
  // organisation — sharing "with your organisation" means nothing when
  // there isn't one (rubric 14's dark-launch invariant). The outcome line
  // is binding copy (rubric 41), so its toast stays.
  const changeVisibility = (next: Visibility) => {
    setError(null);
    update.mutate(
      { visibility: next },
      {
        onSuccess: () => toast.toast({ title: visibilityOutcomeLine(next), tone: "default" }),
        onError: (failure) => setError({ section: "org", text: refusalSentence(failure, SHARE_COPY.orgFailed) }),
      },
    );
  };

  const setMembership = (projectIds: string[]) => {
    setError(null);
    update.mutate(
      { project_ids: projectIds },
      {
        onError: (failure) =>
          setError({ section: "projects", text: refusalSentence(failure, SHARE_COPY.projectsFailed) }),
      },
    );
  };

  // The page shows the new state in place, so a public change needs no
  // toast (P4).
  const toggleIsPublic = (next: boolean, onDone: () => void) => {
    setError(null);
    update.mutate(
      { is_public: next },
      {
        onSuccess: onDone,
        onError: (failure) => setError({ section: "public", text: refusalSentence(failure, SHARE_COPY.publicFailed) }),
      },
    );
  };

  const projectLinks = (ids: readonly string[]) =>
    ids.map((projectId, index) => (
      <span key={projectId}>
        {index > 0 && ", "}
        <Link to={`/projects/${projectId}`} className={PROSE_LINK_CLASS}>
          {projectName.get(projectId) ?? projectId}
        </Link>
      </span>
    ));

  return (
    <main aria-labelledby={titleId} className={cn(LIFECYCLE_PAGE_CLASS, "py-8 max-md:px-0 max-md:py-0")}>
      <h1 id={titleId} className="sr-only">
        {LIFECYCLE_LABELS.share}
      </h1>
      {/* Below md the paper becomes the screen, as the report's does (S9). */}
      <Card className="p-6 max-md:border-0 max-md:p-4 max-md:shadow-none">
        {task.data !== undefined &&
          (isOwner ? (
            <PublicLinkSection
              taskId={taskId}
              isPublic={task.data.is_public}
              pending={update.isPending}
              error={errorFor("public")}
              onToggle={toggleIsPublic}
            />
          ) : (
            <SettingsRow
              headingId={`${titleId}-public`}
              heading={SHARE_COPY.publicHeading}
              state={task.data.is_public ? SHARE_COPY.publicOn : SHARE_COPY.publicOff}
            />
          ))}

        {me.data?.organisation != null && task.data !== undefined && (
          <SettingsRow
            headingId={orgHeadingId}
            heading={SHARE_COPY.orgHeading}
            state={task.data.visibility === "private" ? SHARE_COPY.orgPrivate : SHARE_COPY.orgShared}
            // A task in a project follows the project's visibility, so the
            // control that could only fail is not offered (S4, P3).
            note={
              inProject ? (
                <>
                  {SHARE_COPY.followsProject(memberIds.length)}
                  {projectLinks(memberIds)}.
                </>
              ) : undefined
            }
            control={
              isOwner && !inProject ? (
                <Button
                  variant="outline"
                  className={CONTROL_CLASS}
                  disabled={update.isPending}
                  onClick={() => changeVisibility(task.data?.visibility === "private" ? "org" : "private")}
                >
                  {task.data.visibility === "private" ? SHARE_COPY.shareWithOrg : SHARE_COPY.makePrivate}
                </Button>
              ) : undefined
            }
          >
            <SectionError text={errorFor("org")} />
          </SettingsRow>
        )}

        <SettingsRow headingId={projectsHeadingId} heading={SHARE_COPY.projectsHeading}>
          {memberIds.length === 0 ? (
            <p className="mt-1 text-body text-grey">
              {SHARE_COPY.notInProject}
              {isOwner && projects.data !== undefined && available.length === 0 && (
                <>
                  {" "}
                  {SHARE_COPY.createProject[0]}
                  <Link to="/projects" className={PROSE_LINK_CLASS}>
                    {SHARE_COPY.createProject[1]}
                  </Link>
                  {SHARE_COPY.createProject[2]}
                </>
              )}
            </p>
          ) : (
            <ul className="mt-3 divide-y divide-line border-t border-line">
              {memberIds.map((projectId) => (
                <li key={projectId} className="flex min-h-14 items-center justify-between gap-3">
                  <Link to={`/projects/${projectId}`} className={cn(PROSE_LINK_CLASS, "min-w-0 text-body")}>
                    {projectName.get(projectId) ?? projectId}
                  </Link>
                  {isOwner && (
                    <Button
                      variant="ghost"
                      className={cn(CONTROL_CLASS, "-mr-3 px-3")}
                      onClick={() => setMembership(memberIds.filter((candidate) => candidate !== projectId))}
                      disabled={update.isPending}
                    >
                      {SHARE_COPY.remove}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {isOwner && available.length > 0 && (
            <div className="mt-6 max-w-md">
              <label htmlFor="share-add-to-project" className="mb-2 block text-body font-semibold text-navy">
                {SHARE_COPY.addToProject}
              </label>
              {/* The app's dropdown (round 12): picking a project adds it,
                  and the control goes back to its placeholder. */}
              <Select
                id="share-add-to-project"
                label={SHARE_COPY.addToProject}
                value=""
                placeholder={SHARE_COPY.selectProject}
                options={available.map((project) => ({ value: project.project_id, label: project.name }))}
                disabled={update.isPending}
                onChange={(value) => setMembership([...memberIds, value])}
                className="w-full"
              />
            </div>
          )}
          <SectionError text={errorFor("projects")} />
        </SettingsRow>
      </Card>
    </main>
  );
}
