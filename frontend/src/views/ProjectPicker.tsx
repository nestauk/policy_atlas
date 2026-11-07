import { useEffect, useRef, useState } from "react";

import { useMakeProject } from "./projectActions";
import { PROJECT } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Select } from "../ui/brand/Select";

/** The list's last choice: a project made on the spot. */
const NEW_PROJECT = "new-project";
/** The "None" choice, where the caller offers one. */
const NONE = "none";

type Project = { project_id: string; name: string };

/**
 * A new project's name with "Create" and "Cancel" beside it (round 13;
 * defined once: the picker's "New project…" and the Projects page's form).
 * A Body field, 40 px, focused with its text selected as it opens; Create,
 * or Enter, makes the project (`useMakeProject`); Cancel, or Escape, leaves.
 * A failure keeps the name and says "The project couldn't be created. Try
 * again." under the field.
 *
 * Args:
 *   id: The field's id.
 *   label: The field's name for a screen reader ("New project name").
 *   onCreated: Called with the new project's id and name.
 *   onCancel: Called on Cancel or Escape.
 *   onTyped: Told the name as it is typed.
 */
export function ProjectNameField({
  id,
  label,
  onCreated,
  onCancel,
  onTyped,
}: {
  id: string;
  label: string;
  onCreated: (project: Project) => void;
  onCancel: () => void;
  onTyped?: (name: string) => void;
}) {
  const { make, isPending } = useMakeProject();
  const [name, setName] = useState("");
  const [failed, setFailed] = useState(false);
  const field = useRef<HTMLInputElement>(null);
  useEffect(() => {
    field.current?.focus();
    field.current?.select();
  }, []);
  const create = () => {
    if (name.trim() === "" || isPending) return;
    setFailed(false);
    make(name, {
      onSuccess: ({ projectId, name: made }) => onCreated({ project_id: projectId, name: made }),
      onError: () => setFailed(true),
    });
  };
  const errorId = `${id}-error`;
  return (
    <>
      {/* One row where it fits (the New page, the Share page); in a narrow
          place (the task menu's step) Create and Cancel wrap under it
          together. */}
      <div className="flex flex-wrap items-center gap-2">
        {/* The rename field's rules: Enter creates, Escape cancels. */}
        <input
          ref={field}
          id={id}
          aria-label={label}
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            onTyped?.(event.target.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              create();
            }
            if (event.key === "Escape") {
              event.preventDefault();
              onCancel();
            }
          }}
          aria-invalid={failed || undefined}
          aria-describedby={failed ? errorId : undefined}
          className="h-10 min-w-[12rem] flex-1 border border-line-2 bg-paper px-3 text-body text-ink focus-visible:outline-2 focus-visible:outline-blue"
        />
        <span className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="h-10 shrink-0 whitespace-nowrap py-0"
            disabled={name.trim() === "" || isPending}
            onClick={create}
          >
            Create
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="h-10 shrink-0 whitespace-nowrap px-3 py-0 text-body"
            onClick={onCancel}
          >
            Cancel
          </Button>
        </span>
      </div>
      {failed && (
        <p id={errorId} role="alert" className="mt-2 text-body text-red">
          The {PROJECT.lower} couldn't be created. Try again.
        </p>
      )}
    </>
  );
}

/**
 * The project dropdown with "New project…" at its end (owner, round 13;
 * defined once for the New page and the task menu's "Add to project").
 *
 * "New project…" swaps the dropdown for `ProjectNameField` on the same row
 * and width. Create makes the project at once and brings the dropdown back
 * with it chosen; the new project is listed here until the caller's
 * projects refetch carries it. Cancel brings the dropdown back with nothing
 * chosen.
 *
 * Args:
 *   id: The dropdown's id (a visible label points at it; focus comes back
 *     to it after Create or Cancel).
 *   label: The dropdown's name.
 *   value: The chosen project's id, or "" for none.
 *   projects: The projects to offer, in order.
 *   onChange: Called with the chosen project's id, or "" for none.
 *   noneLabel: When set, a first choice with these words standing for no
 *     project (the New page's "None"); omitted, the dropdown shows
 *     `placeholder` until a project is chosen (the menu's step).
 *   placeholder: The dropdown's words before a choice, without `noneLabel`.
 *   disabled: Inert while the caller's own change runs.
 *   onNaming: Told the typed name while the field is open, and null when it
 *     closes, so a caller can act on a name not yet created.
 *   size: The dropdown's height, as `Select`'s.
 */
export function ProjectPicker({
  id,
  label,
  value,
  projects,
  onChange,
  noneLabel,
  placeholder,
  disabled = false,
  onNaming,
  size = 40,
}: {
  id: string;
  label: string;
  value: string;
  projects: ReadonlyArray<Project>;
  onChange: (projectId: string) => void;
  noneLabel?: string;
  placeholder?: string;
  disabled?: boolean;
  onNaming?: (name: string | null) => void;
  size?: 32 | 40;
}) {
  const [naming, setNaming] = useState(false);
  const [made, setMade] = useState<Project[]>([]);

  const close = () => {
    setNaming(false);
    onNaming?.(null);
    window.setTimeout(() => document.getElementById(id)?.focus(), 0);
  };

  if (naming) {
    return (
      <ProjectNameField
        id={`${id}-new`}
        label={`New ${PROJECT.lower} name`}
        onTyped={(name) => onNaming?.(name)}
        onCreated={(project) => {
          setMade((list) => [...list, project]);
          onChange(project.project_id);
          close();
        }}
        onCancel={() => {
          onChange("");
          close();
        }}
      />
    );
  }

  const listed = [...projects, ...made.filter((project) => !projects.some((p) => p.project_id === project.project_id))];
  return (
    <Select
      id={id}
      label={label}
      value={value === "" ? (noneLabel !== undefined ? NONE : "") : value}
      placeholder={placeholder}
      size={size}
      disabled={disabled}
      options={[
        ...(noneLabel !== undefined ? [{ value: NONE, label: noneLabel }] : []),
        ...listed.map((project) => ({ value: project.project_id, label: project.name })),
        { value: NEW_PROJECT, label: `New ${PROJECT.lower}…` },
      ]}
      onChange={(next) => {
        if (next === NEW_PROJECT) {
          setNaming(true);
          onNaming?.("");
          return;
        }
        onChange(next === NONE ? "" : next);
      }}
      className="w-full"
    />
  );
}
