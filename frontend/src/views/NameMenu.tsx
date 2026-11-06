import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";

import { useArchiveProject, useUpdateProject } from "../api/mutations";
import { PROJECT, TASK } from "../lib/vocabulary";

import { scrub } from "../lib/scrub";
import { Button, buttonVariants } from "../ui/brand/Button";
import { cn } from "../ui/brand/cn";
import { ChevronIcon } from "../ui/brand/icons";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { MENU_ITEM_CLASS, moveMenuFocus } from "../ui/radix/menu";

/** The header's 40 px controls (Save, Cancel, the confirm's two buttons). */
const CONTROL_CLASS = "h-10 whitespace-nowrap py-0";
const OUTLINE_CONTROL_CLASS = cn(buttonVariants({ variant: "outline" }), CONTROL_CLASS);

/** One mutation the menu runs: it calls back once it has settled. */
type Action<T> = (value: T, done: { onSuccess: () => void; onError: () => void }) => void;

/**
 * A task's or a project's name with its menu (task 058, owner round 11): the
 * name, anything that follows it on its baseline (the task's capability),
 * and a 40 px quiet control with the chevron that opens Rename and Archive.
 *
 * The menu is the popover's tokens with menu rows (the account menu's rows):
 * focus moves to the first item as it opens, the arrow keys move between
 * items, and Escape or an outside press closes it with focus back on the
 * chevron. Rename closes the menu and turns the name into a field in place,
 * with Save and Cancel beside it (Enter saves, Escape cancels); focus comes
 * back to the chevron when it closes. Archive asks once more in words, the
 * Share page's two-step confirm: a sentence that says what it does, taking
 * focus, then "Archive" and "Keep it".
 *
 * Only an owner sees the chevron; a colleague sees the name alone.
 */
export function NameMenu({
  name,
  label,
  fieldLabel,
  titleClassName,
  after,
  canEdit,
  rename,
  renameError,
  archive,
  archiveSentence,
  archiveError,
  pending = false,
  wrap = false,
}: {
  name: string;
  /** The chevron's name ("Task settings"). */
  label: string;
  /** The rename field's name ("Task name"). */
  fieldLabel: string;
  /** The name's type: the header's title size. */
  titleClassName: string;
  /** What follows the name on its baseline (the capability, in grey). */
  after?: ReactNode;
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
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [draft, setDraft] = useState(name);
  const [failed, setFailed] = useState<"rename" | "archive" | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const sentence = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (editing) {
      field.current?.focus();
      field.current?.select();
    }
  }, [editing]);
  // The confirm step takes focus on its sentence, so a screen reader hears
  // what archiving does first and a second Enter does not archive.
  useEffect(() => {
    if (confirming) sentence.current?.focus();
  }, [confirming]);

  const backToTrigger = () => window.setTimeout(() => trigger.current?.focus(), 0);
  const stopEditing = () => {
    setEditing(false);
    setFailed(null);
    setDraft(name);
    backToTrigger();
  };
  const save = () => {
    const next = draft.trim();
    if (next === "" || pending) return;
    if (next === name) {
      stopEditing();
      return;
    }
    rename(next, { onSuccess: stopEditing, onError: () => setFailed("rename") });
  };

  const title = <span className={cn("min-w-0", wrap ? "text-pretty" : "truncate", titleClassName)}>{scrub(name)}</span>;

  // Phrasing content only (spans, an input, buttons), so the same markup
  // sits in the task bar and inside a page's h1.
  if (editing) {
    return (
      <span
        role="group"
        aria-label={`${label}: rename`}
        className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1"
        onKeyDown={(event) => {
          // Escape anywhere here (the field, Save, Cancel) leaves it.
          if (event.key === "Escape") {
            event.preventDefault();
            stopEditing();
          }
        }}
      >
        <label className="sr-only" htmlFor="name-menu-field">
          {fieldLabel}
        </label>
        <input
          ref={field}
          id="name-menu-field"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              save();
            }
          }}
          aria-invalid={failed === "rename" || undefined}
          aria-describedby={failed === "rename" ? "name-menu-error" : undefined}
          className={cn(
            "min-w-0 flex-1 basis-56 border border-line-2 bg-paper px-2 py-0.5 md:max-w-[36rem]",
            titleClassName,
          )}
        />
        <span className="flex shrink-0 items-center gap-1">
          <button type="button" className={OUTLINE_CONTROL_CLASS} disabled={draft.trim() === "" || pending} onClick={save}>
            Save name
          </button>
          <Button type="button" variant="ghost" className={cn(CONTROL_CLASS, "px-3 text-body")} onClick={stopEditing}>
            Cancel
          </Button>
        </span>
        {failed === "rename" && (
          <span id="name-menu-error" role="alert" className="basis-full text-meta font-normal tracking-normal text-red">
            {renameError}
          </span>
        )}
      </span>
    );
  }

  return (
    // A page title wraps as text, the chevron after its last word; the task
    // bar's name keeps one line with what follows on its baseline.
    <span className={wrap ? "min-w-0" : "flex min-w-0 flex-wrap items-baseline gap-x-3"}>
      {title}
      {after}
      {canEdit && (
        <Popover
          open={open}
          onOpenChange={(next) => {
            setOpen(next);
            if (!next) {
              setConfirming(false);
              setFailed(null);
            }
          }}
        >
          <PopoverTrigger asChild>
            {/* A 40 px quiet control: the chevron, Grey, Navy on hover, the
                Blue Wash while the menu is open; it sits on the name's line. */}
            <button
              ref={trigger}
              type="button"
              aria-label={label}
              aria-haspopup="menu"
              title={label}
              className={cn(
                "pressable inline-flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center text-grey",
                wrap ? "ml-2 align-middle" : "-ml-1.5 self-center",
                "transition-colors duration-150 hover:bg-blue-tint-2 hover:text-navy",
                "data-[state=open]:bg-blue-tint-2 data-[state=open]:text-navy",
              )}
            >
              <ChevronIcon className="rotate-90" />
            </button>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            className={cn("p-0", confirming ? "w-80" : "w-auto min-w-60")}
            onOpenAutoFocus={(event) => {
              event.preventDefault();
              menu.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
            }}
          >
            {confirming ? (
              <div
                role="group"
                aria-labelledby="name-menu-confirm"
                className="p-4"
              >
                <p id="name-menu-confirm" ref={sentence} tabIndex={-1} className="text-body text-ink focus-visible:outline-none">
                  {archiveSentence}
                </p>
                {failed === "archive" && (
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
                        onError: () => setFailed("archive"),
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
                      backToTrigger();
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
                    setDraft(name);
                    setEditing(true);
                  }}
                >
                  Rename
                </button>
                {archive !== undefined && (
                  <button type="button" role="menuitem" className={MENU_ITEM_CLASS} onClick={() => setConfirming(true)}>
                    Archive
                  </button>
                )}
              </div>
            )}
          </PopoverContent>
        </Popover>
      )}
    </span>
  );
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
}: {
  projectId: string;
  name: string;
  isOwner: boolean;
  archived: boolean;
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
      archiveSentence={`Archiving removes this ${PROJECT.lower} from your active ${PROJECT.lowerMany}. Its ${TASK.lowerMany} stay as they are.`}
      archiveError={`The ${PROJECT.lower} couldn't be archived. Try again.`}
    />
  );
}
