import { useEffect, useId, useRef, useState, type ReactElement, type ReactNode } from "react";
import { useNavigate } from "react-router";

import { useArchiveProject, useUpdateProject } from "../api/mutations";
import { useProjects } from "../api/queries";
import { PROJECT, TASK } from "../lib/vocabulary";

import { Button, buttonVariants } from "../ui/brand/Button";
import { cn } from "../ui/brand/cn";
import { ChevronIcon } from "../ui/brand/icons";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { MENU_ITEM_CLASS, moveMenuFocus } from "../ui/radix/menu";
import { useAddTaskToProject } from "./projectActions";
import { ChangingText } from "./workspace/ChangingText";
import { ProjectPicker } from "./ProjectPicker";
import { SHARE_COPY } from "./sharePresentation";

/** The header's 40 px controls (Save, Cancel, the confirm's two buttons). */
const CONTROL_CLASS = "h-10 whitespace-nowrap py-0";
const OUTLINE_CONTROL_CLASS = cn(buttonVariants({ variant: "outline" }), CONTROL_CLASS);

/** The rename field's button: "Save" on screen (owner, round 13), named
 *  "Save name" for a screen reader, on the headers and the rows alike. */
const SAVE_WORD = "Save";
const SAVE_NAME_LABEL = "Save name";

/** One mutation the menu runs: it calls back once it has settled. */
export type Action<T> = (value: T, done: { onSuccess: () => void; onError: () => void }) => void;

/** A further step a menu item opens in place of the menu (round 12). */
export type MenuStep = {
  /** The item's words ("Add to project"). */
  label: string;
  /** Why it cannot be chosen now; the item is disabled while it is set. */
  reason?: string;
  /** The step's body; `close` shuts the menu with focus back on its control. */
  render: (controls: { close: () => void }) => ReactNode;
};

/**
 * The rename field (task 058, owner round 11; split out in round 12 so the
 * list rows use it too): the name as a field in place, with Save and
 * Cancel beside it. Enter saves, Escape (anywhere in the group) cancels; a
 * failed save is said under the field. `onClose` runs when it closes either
 * way, for the caller to put focus back on its control.
 *
 * Phrasing content only (spans, an input, buttons), so the same markup sits
 * in the task bar, inside a page's h1 and in a list row.
 */
export function NameRenameField({
  name,
  label,
  fieldLabel,
  titleClassName,
  rename,
  renameError,
  pending = false,
  onClose,
  below,
}: {
  name: string;
  /** The control's name ("Task settings"); the group is "<label>: rename". */
  label: string;
  /** The field's name ("Task name"). */
  fieldLabel: string;
  /** The field's type: the name's own size where it sits. */
  titleClassName: string;
  rename: Action<string>;
  /** Said under the field when a save fails. */
  renameError: string;
  pending?: boolean;
  onClose: () => void;
  /** The short line under the name, kept under the field. */
  below?: ReactNode;
}) {
  const [draft, setDraft] = useState(name);
  const [failed, setFailed] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  const id = useId();
  const fieldId = `${id}-field`;
  const errorId = `${id}-error`;

  useEffect(() => {
    field.current?.focus();
    field.current?.select();
  }, []);

  const save = () => {
    const next = draft.trim();
    if (next === "" || pending) return;
    if (next === name) {
      onClose();
      return;
    }
    rename(next, { onSuccess: onClose, onError: () => setFailed(true) });
  };

  return (
    <span
      role="group"
      aria-label={`${label}: rename`}
      className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1"
      onKeyDown={(event) => {
        // Escape anywhere here (the field, Save, Cancel) leaves it.
        if (event.key === "Escape") {
          event.preventDefault();
          onClose();
        }
      }}
    >
      <label className="sr-only" htmlFor={fieldId}>
        {fieldLabel}
      </label>
      <input
        ref={field}
        id={fieldId}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            save();
          }
        }}
        aria-invalid={failed || undefined}
        aria-describedby={failed ? errorId : undefined}
        className={cn(
          "min-w-0 flex-1 basis-56 border border-line-2 bg-paper px-2 py-0.5 md:max-w-[36rem]",
          titleClassName,
        )}
      />
      <span className="flex shrink-0 items-center gap-1">
        {/* The visible word is "Save" (owner, round 13); the name keeps the
            word it saves, which holds the visible word (label in name). */}
        <button
          type="button"
          aria-label={SAVE_NAME_LABEL}
          className={OUTLINE_CONTROL_CLASS}
          disabled={draft.trim() === "" || pending}
          onClick={save}
        >
          {SAVE_WORD}
        </button>
        <Button type="button" variant="ghost" className={cn(CONTROL_CLASS, "px-3 text-body")} onClick={onClose}>
          Cancel
        </Button>
      </span>
      {failed && (
        <span id={errorId} role="alert" className="basis-full text-meta font-normal tracking-normal text-red">
          {renameError}
        </span>
      )}
      {below !== undefined && <span className="basis-full">{below}</span>}
    </span>
  );
}

/**
 * The menu behind a name's control (task 058, owner round 11; split out in
 * round 12 so the list rows open the same menu): Rename and Archive as menu
 * rows (the account menu's rows), focus on the first as it opens, the arrow
 * keys moving between them; Escape or an outside press closes it with focus
 * back on the control. Archive asks once more in words, the Share page's
 * two-step confirm: a sentence that says what it does, taking focus, then
 * "Archive" and "Keep it".
 *
 * `trigger` is the control itself (a button; the popover wraps it with
 * `asChild`). `onRename` runs as the menu closes for Rename. `returnFocus`
 * puts focus back on the control after "Keep it".
 */
export function NameActionsMenu({
  label,
  trigger,
  onRename,
  archive,
  archiveSentence,
  archiveError,
  pending = false,
  align = "start",
  returnFocus,
  steps = [],
}: {
  /** The menu's name, the control's ("Task settings"). */
  label: string;
  trigger: ReactElement;
  onRename: () => void;
  /** More items between Rename and Archive, each opening its own step in
   *  the menu (a list row's "Add to project", round 12). An item with a
   *  `reason` is disabled, the reason on a grey line under its words. */
  steps?: ReadonlyArray<MenuStep>;
  /** Absent when the thing cannot be archived from here. */
  archive?: Action<void>;
  /** The confirm's sentence: what archiving does. */
  archiveSentence: string;
  /** Said in the menu when an archive fails. */
  archiveError: string;
  pending?: boolean;
  align?: "start" | "end";
  returnFocus: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [failed, setFailed] = useState(false);
  const [stepAt, setStepAt] = useState<number | null>(null);
  const menu = useRef<HTMLDivElement>(null);
  const sentence = useRef<HTMLParagraphElement>(null);
  const stepBox = useRef<HTMLDivElement>(null);
  const confirmId = useId();

  // A step takes focus on its first control as it opens.
  useEffect(() => {
    if (stepAt !== null) stepBox.current?.querySelector<HTMLElement>("button:not([disabled]), input")?.focus();
  }, [stepAt]);
  const closeMenu = () => {
    setOpen(false);
    setStepAt(null);
  };
  const step = stepAt !== null ? steps[stepAt] : undefined;

  // The confirm step takes focus on its sentence, so a screen reader hears
  // what archiving does first and a second Enter does not archive.
  useEffect(() => {
    if (confirming) sentence.current?.focus();
  }, [confirming]);

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setConfirming(false);
          setFailed(false);
          setStepAt(null);
        }
      }}
    >
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent
        align={align}
        className={cn("p-0", confirming || step !== undefined ? "w-80" : "w-auto min-w-60")}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          menu.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
        }}
      >
        {step !== undefined ? (
          <div ref={stepBox} className="p-4">
            {step.render({
              close: () => {
                closeMenu();
                returnFocus();
              },
            })}
          </div>
        ) : confirming ? (
          <div role="group" aria-labelledby={confirmId} className="p-4">
            <p id={confirmId} ref={sentence} tabIndex={-1} className="text-body text-ink focus-visible:outline-none">
              {archiveSentence}
            </p>
            {failed && (
              <p role="alert" className="mt-2 text-meta text-red">
                {archiveError}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                className={OUTLINE_CONTROL_CLASS}
                disabled={pending}
                onClick={() =>
                  archive?.(undefined, {
                    onSuccess: () => {
                      setOpen(false);
                      setConfirming(false);
                    },
                    onError: () => setFailed(true),
                  })
                }
              >
                Archive
              </button>
              <Button
                type="button"
                variant="ghost"
                className={cn(CONTROL_CLASS, "px-3 text-body")}
                disabled={pending}
                onClick={() => {
                  setConfirming(false);
                  setOpen(false);
                  returnFocus();
                }}
              >
                Keep it
              </Button>
            </div>
          </div>
        ) : (
          <div
            ref={menu}
            role="menu"
            aria-label={label}
            aria-orientation="vertical"
            className="py-1"
            onKeyDown={(event) => moveMenuFocus(event, menu.current)}
          >
            <button
              type="button"
              role="menuitem"
              className={MENU_ITEM_CLASS}
              onClick={() => {
                setOpen(false);
                onRename();
              }}
            >
              Rename
            </button>
            {steps.map((item, index) => (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                disabled={item.reason !== undefined}
                className={cn(
                  MENU_ITEM_CLASS,
                  item.reason !== undefined &&
                    "h-auto min-h-10 cursor-default flex-col items-start justify-center py-2 text-grey hover:bg-transparent hover:text-grey",
                )}
                onClick={() => setStepAt(index)}
              >
                <span>{item.label}</span>
                {item.reason !== undefined && (
                  <span className="block text-caption font-normal text-grey">{item.reason}</span>
                )}
              </button>
            ))}
            {archive !== undefined && (
              <button type="button" role="menuitem" className={MENU_ITEM_CLASS} onClick={() => setConfirming(true)}>
                Archive
              </button>
            )}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}

/**
 * A task's or a project's name with its menu (task 058, owner round 11): the
 * name, a 40 px quiet control with the chevron that opens Rename and Archive
 * (`NameActionsMenu`) sitting on the name's baseline, and anything that goes
 * under the name on its own short line (the task's capability; owner, round
 * 12). Rename closes the menu and turns the name into a field in place
 * (`NameRenameField`); focus comes back to the chevron when it closes.
 *
 * Only an owner sees the chevron; a colleague sees the name alone.
 */
export function NameMenu({
  name,
  label,
  fieldLabel,
  titleClassName,
  below,
  canEdit,
  rename,
  renameError,
  archive,
  archiveSentence,
  archiveError,
  pending = false,
  wrap = false,
  steps,
}: {
  name: string;
  /** The chevron's name ("Task settings"). */
  label: string;
  /** The rename field's name ("Task name"). */
  fieldLabel: string;
  /** The name's type: the header's title size. */
  titleClassName: string;
  /** The short line under the name (the capability, in grey). */
  below?: ReactNode;
  canEdit: boolean;
  rename: Action<string>;
  /** Said under the field when a save fails. */
  renameError: string;
  /** Absent when the thing cannot be archived from here. */
  archive?: Action<void>;
  /** The confirm's sentence: what archiving does. */
  archiveSentence: string;
  /** Said in the menu when an archive fails. */
  archiveError: string;
  pending?: boolean;
  /** A page title wraps; the task bar's name truncates on its one line. */
  wrap?: boolean;
  /** More menu items between Rename and Archive (the task's "Add to
   *  project", round 12); a project's title has none. */
  steps?: ReadonlyArray<MenuStep>;
}) {
  const [editing, setEditing] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const backToTrigger = () => window.setTimeout(() => trigger.current?.focus(), 0);

  // A backend rename is revealed as a generation; the reader's own rename
  // remounts the title with the new name, so it just commits.
  const title = <ChangingText text={name} wrap={wrap} className={titleClassName} testIdPrefix="name" />;

  if (editing) {
    return (
      <NameRenameField
        name={name}
        label={label}
        fieldLabel={fieldLabel}
        titleClassName={titleClassName}
        rename={rename}
        renameError={renameError}
        pending={pending}
        below={below}
        onClose={() => {
          setEditing(false);
          backToTrigger();
        }}
      />
    );
  }

  const chevronMenu = canEdit && (
    <NameActionsMenu
      label={label}
      onRename={() => {
        setEditing(true);
      }}
      archive={archive}
      archiveSentence={archiveSentence}
      archiveError={archiveError}
      pending={pending}
      returnFocus={backToTrigger}
      steps={steps}
      trigger={
        // A 40 px quiet control: the chevron, Grey, Navy on hover, the Blue
        // Wash while the menu is open; it sits on the name's line. On the
        // name's baseline: the button's baseline is its glyph box's foot,
        // and the glyph drops 3 px so the chevron's foot rests on the line
        // like a letter's; the negative margins keep the 40 px box from
        // growing the name's line.
        <button
          ref={trigger}
          type="button"
          aria-label={label}
          aria-haspopup="menu"
          title={label}
          className={cn(
            "pressable inline-flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center text-grey -my-2",
            wrap ? "ml-1 align-baseline" : "ml-0.5 self-baseline",
            // While a backend rename is revealed the chevron fades out and
            // back (opacity only: it keeps its place and its focus).
            "transition-[color,background-color,opacity] duration-150 hover:bg-blue-tint-2 hover:text-navy peer-data-[changing=true]:opacity-0",
            "data-[state=open]:bg-blue-tint-2 data-[state=open]:text-navy",
          )}
        >
          <ChevronIcon className="translate-y-[3px] rotate-90" />
        </button>
      }
    />
  );

  // A page title wraps as text, the chevron after its last word; the task
  // bar's name keeps one line, the chevron on its baseline and the short
  // line under it.
  if (wrap) {
    return (
      <span className="min-w-0">
        {title}
        {chevronMenu}
      </span>
    );
  }
  return (
    <span className="flex min-w-0 flex-col">
      <span className="flex min-w-0 items-baseline">
        {title}
        {chevronMenu}
      </span>
      {below}
    </span>
  );
}

/**
 * A task's "Add to project" step (owner, rounds 12 and 13; the task header's
 * menu and the list rows' share it): the shared `ProjectPicker` (the New page
 * and the Share page use the same one) listing the projects the task is not
 * in, then "New project…", which makes a project on the spot and chooses
 * it; then "Add" and "Cancel". A refusal is said in the step.
 */
function AddToProjectStep({
  label,
  placeholder,
  projects,
  add,
  error,
  pending,
  close,
}: {
  /** The dropdown's visible label and name ("Add to a project"). */
  label: string;
  /** The dropdown's words before a choice ("Select a project"). */
  placeholder: string;
  projects: ReadonlyArray<{ project_id: string; name: string }>;
  add: Action<string>;
  /** Said in the step when the change fails. */
  error: string;
  pending: boolean;
  close: () => void;
}) {
  const [chosen, setChosen] = useState("");
  const [failed, setFailed] = useState(false);
  // While a new project is named, its own Create and Cancel are the step's
  // only buttons: one Cancel on screen, not two.
  const [naming, setNaming] = useState(false);
  const id = useId();
  return (
    <div role="group" aria-labelledby={`${id}-label`}>
      <label id={`${id}-label`} htmlFor={id} className="mb-2 block text-meta font-semibold text-navy">
        {label}
      </label>
      <ProjectPicker
        id={id}
        label={label}
        value={chosen}
        placeholder={placeholder}
        projects={projects}
        onChange={(value) => {
          setChosen(value);
          setFailed(false);
        }}
        disabled={pending}
        onNaming={(name) => setNaming(name !== null)}
      />
      {failed && (
        <p role="alert" className="mt-2 text-meta text-red">
          {error}
        </p>
      )}
      <div className={cn("mt-3 flex flex-wrap gap-2", naming && "hidden")}>
        <button
          type="button"
          className={OUTLINE_CONTROL_CLASS}
          disabled={chosen === "" || pending}
          onClick={() => add(chosen, { onSuccess: close, onError: () => setFailed(true) })}
        >
          Add
        </button>
        <Button type="button" variant="ghost" className={cn(CONTROL_CLASS, "px-3 text-body")} onClick={close}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

/**
 * The "Add to project" item for a task's menu (owner, rounds 12 and 13): the
 * same item and step on the task header's menu and on a task row's, so the
 * two menus match. It lists the projects the Share page offers (one cached
 * `useProjects` query) less those the task is already in, then "New
 * project…", and adds the task through `useAddTaskToProject`, the Share
 * page's same change. It is never disabled: a task in
 * every project still has "New project…".
 *
 * Args:
 *   taskId: The task.
 *   projectIds: The task's projects now.
 *
 * Returns:
 *   The menu step to pass as `steps`.
 */
export function useAddToProjectStep(taskId: string, projectIds: readonly string[] | null | undefined): MenuStep {
  const projects = useProjects();
  const { add, isPending } = useAddTaskToProject(taskId, projectIds);
  const memberIds = projectIds ?? [];
  const available = (projects.data?.data ?? []).filter((project) => !memberIds.includes(project.project_id));
  return {
    label: `Add to ${PROJECT.lower}`,
    render: ({ close }) => (
      <AddToProjectStep
        label={SHARE_COPY.addToProject}
        placeholder={SHARE_COPY.selectProject}
        projects={available}
        add={(projectId, done) => add(projectId, { onSuccess: done.onSuccess, onError: done.onError })}
        error={SHARE_COPY.projectsFailed}
        pending={isPending}
        close={close}
      />
    ),
  };
}

/**
 * The project archive confirm's sentence (owner, round 14): what happens to
 * the project and to its tasks. Archiving also archives the tasks that are
 * in no other project; the server counts them on the project row
 * (`ProjectOut.solo_task_count`, the backend builder's this round), and the
 * clause is left out when there are none or the count is not known yet.
 *
 * Args:
 *   soloTaskCount: How many of the project's tasks are in no other project.
 *
 * Returns:
 *   One plain sentence.
 */
export function projectArchiveSentence(soloTaskCount: number | null | undefined): string {
  const base = `Archiving removes this ${PROJECT.lower} from your active ${PROJECT.lowerMany}`;
  if (soloTaskCount == null || soloTaskCount <= 0) return `${base}.`;
  const tasks = soloTaskCount === 1 ? `1 ${TASK.lower}` : `${soloTaskCount} ${TASK.lowerMany}`;
  return `${base} and archives its ${tasks} that ${soloTaskCount === 1 ? "is" : "are"} in no other ${PROJECT.lower}.`;
}

/** The project row's count of tasks in no other project, typed here until
 *  the generated `ProjectOut` carries it (round 14). */
export function soloTaskCount(project: object): number | null {
  const value = (project as { solo_task_count?: unknown }).solo_task_count;
  return typeof value === "number" ? value : null;
}

/**
 * A project page's title with the same menu as a task's (owner, round 11:
 * "add a way to archive (and rename) projects"). Rename saves in place;
 * Archive, once confirmed, leaves the page for the Projects list. An
 * archived project offers Rename only.
 */
export function ProjectName({
  projectId,
  name,
  isOwner,
  archived,
  soloTasks = null,
}: {
  projectId: string;
  name: string;
  isOwner: boolean;
  archived: boolean;
  /** Its tasks in no other project, for the archive sentence (round 14). */
  soloTasks?: number | null;
}) {
  const update = useUpdateProject(projectId);
  const archive = useArchiveProject(projectId);
  const navigate = useNavigate();
  return (
    <NameMenu
      wrap
      name={name}
      label={`${PROJECT.one} settings`}
      fieldLabel={`${PROJECT.one} name`}
      titleClassName=""
      canEdit={isOwner}
      pending={update.isPending || archive.isPending}
      rename={(next, done) => update.mutate({ name: next }, { onSuccess: done.onSuccess, onError: done.onError })}
      renameError={`The ${PROJECT.lower} couldn't be renamed. Try again.`}
      archive={
        archived
          ? undefined
          : (_, done) =>
              archive.mutate(undefined, {
                onSuccess: () => {
                  done.onSuccess();
                  void navigate("/projects");
                },
                onError: done.onError,
              })
      }
      archiveSentence={projectArchiveSentence(soloTasks)}
      archiveError={`The ${PROJECT.lower} couldn't be archived. Try again.`}
    />
  );
}
