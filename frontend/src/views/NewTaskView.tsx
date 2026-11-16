import { useState } from "react";
import { blobUrl } from "../lib/blobUrl";
import { useNavigate, useSearchParams } from "react-router";

import { useProjects, useTasks } from "../api/queries";
import { useCreateTask } from "../api/mutations";
import {
  CAPABILITIES,
  type SelectableCapabilityKey,
  isSelectableCapability,
} from "../lib/capabilities";
import { useDocumentTitle } from "../lib/title";
import { COPY, PROJECT, TASK } from "../lib/vocabulary";
import { Button, buttonVariants } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import { CloseButton } from "../ui/brand/CloseButton";
import { PaperclipIcon } from "../ui/brand/icons";
import { MultiSelect } from "../ui/brand/MultiSelect";
import { cn } from "../ui/brand/cn";
import { LINK_CLASS } from "../ui/brand/inlineActions";
import { CAPTION_LABEL_CLASS } from "../ui/brand/label";
import { useMakeProject } from "./projectActions";
import { ProjectPicker } from "./ProjectPicker";
import { AttachFileButton } from "./toc/uploads";
import type { TocUploadHandOff } from "./workspace/TaskAgentPane";

/** Step one: pick a kind of work. Two of the four can run. */
function CapabilityList({ onPick }: { onPick: (key: SelectableCapabilityKey) => void }) {
  return (
    <ul role="list" className="mt-10 flex flex-col">
      {CAPABILITIES.map((capability) =>
        capability.available ? (
          <li key={capability.key}>
            <button
              type="button"
              onClick={() => onPick(capability.key as SelectableCapabilityKey)}
              className="flex w-full cursor-pointer items-center justify-between gap-4 border-b border-line px-0.5 py-3.5 text-left text-lead font-normal leading-[25px] text-navy max-md:text-body max-md:leading-snug hover:text-blue"
            >
              <span>{capability.name}</span>
              <span aria-hidden="true" className="shrink-0 text-blue">
                →
              </span>
            </button>
          </li>
        ) : (
          <li key={capability.key}>
            {/* Not a button and not focusable: a control whose only possible
                outcome is failure should not be reachable at all. */}
            <div
              aria-disabled="true"
              className="flex items-center justify-between gap-4 border-b border-line px-0.5 py-3.5 select-none"
            >
              <span className="text-lead font-normal leading-[25px] text-grey max-md:text-body max-md:leading-snug">{capability.name}</span>
              <span className={cn(CAPTION_LABEL_CLASS, "shrink-0")}>
                {COPY.comingSoon}
              </span>
            </div>
          </li>
        ),
      )}
    </ul>
  );
}

/** The help line under "Evidence search to start from" (owner, round 14). */
export const START_FROM_HELP =
  "Optional. Start from a completed evidence search in the same project to draw from its sources and report.";

/** The label and one plain sentence over each optional field (owner, round
 *  13: "Starts from" was unclear in user testing). */
const FIELD_LABEL_CLASS = "block text-body font-semibold text-navy";
const FIELD_HELP_CLASS = "mt-1 max-w-prose text-body font-normal text-grey";

/** A finished Evidence search a scoping task can start from (owner, round
 *  14): one the reader owns whose latest walk finished. The page offers the
 *  chosen project's only. */
type LinkableSearch = { task_id: string; name: string; project_ids: string[] };

function linkableSearches(
  rows: ReadonlyArray<{
    task_id: string;
    name: string;
    capability?: string | null;
    is_owner?: boolean;
    project_ids?: string[] | null;
    latest_run?: { status: string } | null;
  }>,
): LinkableSearch[] {
  return rows
    .filter(
      (task) =>
        task.capability === "evidence_search" &&
        task.is_owner !== false &&
        (task.latest_run?.status === "succeeded" || task.latest_run?.status === "degraded"),
    )
    .map((task) => ({ task_id: task.task_id, name: task.name, project_ids: task.project_ids ?? [] }));
}

/** Per-capability copy for step two. The form SHAPE is the same for both in
 *  this slice — question, project and (scoping only) the search to start
 *  from, no depth
 *  or job control (contract second-round amendment 2) — so only the words
 *  differ. Options scoping's submit reads "Prepare plan" (task 044, phase
 *  3.4): the task's own plan is what the next screen opens on. */
const FORM_COPY: Record<
  SelectableCapabilityKey,
  { heading: string; blurb: string; placeholder: string; submitLabel: string }
> = {
  evidence_search: {
    heading: "What do you need evidence on?",
    blurb:
      "Ask a policy question. Policy Atlas will clarify what you need, draft a search plan for your review, then find the evidence.",
    placeholder: "e.g. What works to reduce childhood obesity in the UK?",
    submitLabel: "Start",
  },
  options_scoping: {
    heading: "What are you trying to change?",
    blurb:
      "Describe the change you want. Policy Atlas will clarify what you need, draft a plan for your review, then set out what happens if nothing changes.",
    placeholder: "e.g. How can we reduce the number of young people not in education, employment or training?",
    submitLabel: "Prepare plan",
  },
  theory_of_change: {
    heading: "What change do you want to explain?",
    blurb:
      "Describe the change you want or the intervention you have in mind. Policy Atlas will draft a theory of change and check each step against evidence.\nIf you have an already existing theory of change, upload it as an image or PDF and Policy Atlas will check it against evidence.",
    placeholder:
      "Describe the change you want, the intervention you have in mind, or paste a theory of change you already have.",
    submitLabel: "Start",
  },
};

/** Upload your own theory of change: a paperclip, then the picked file with a way to remove it. */
function AttachTheory({ file, onFile }: { file: File | null; onFile: (file: File | null) => void }) {
  const url = file !== null && file.type !== "application/pdf" ? blobUrl(file) : null;
  if (file !== null) {
    return (
      <div className="flex min-w-0 shrink-0 items-center gap-2 border border-line bg-paper py-1 pr-1 pl-3">
        {url !== null ? <img src={url} alt="" className="h-10 w-14 object-contain" /> : <PaperclipIcon className="shrink-0 text-grey" />}
        <span className="max-w-[14rem] truncate text-meta font-semibold text-navy">{file.name}</span>
        <CloseButton aria-label={`Remove ${file.name}`} onClick={() => onFile(null)} />
      </div>
    );
  }
  return (
    <AttachFileButton
      onFile={onFile}
      className={cn(buttonVariants({ variant: "outline" }), "shrink-0 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-blue")}
      iconClassName="shrink-0"
    >
      Upload your theory
    </AttachFileButton>
  );
}

/** Step two: the question, and as little else as possible beside it. */
function QuestionForm({ capability }: { capability: SelectableCapabilityKey }) {
  const [searchParams] = useSearchParams();
  const presetProject = searchParams.get("project") ?? "";
  const [question, setQuestion] = useState("");
  const [projectId, setProjectId] = useState(presetProject);
  // Options scoping only: the Evidence searches it starts from, none by
  // default (owner, round 13: several again, `from_task_ids` is a list).
  const [fromTaskIds, setFromTaskIds] = useState<string[]>([]);
  // The projects the task menu's "Add to project" offers (one cached query).
  // Every task this caller can read is a valid target: assignment resolves
  // under the colleague-mutation grade (owner ruling 2026-08-27).
  const projects = useProjects();
  const assignableProjects = projects.data?.data ?? [];
  // The searches a scoping task can start from: the reader's own finished
  // Evidence searches (owner, round 14). Owned is
  // read off the rows (`is_owner`), so a caller without an organisation
  // sends no `scope` (rubric 14's dark-launch invariant).
  const tasks = useTasks({ status: "active", page_size: 200 }, { enabled: capability === "options_scoping" });
  // While a new project is being named (`ProjectPicker`'s field is open),
  // the typed name; null otherwise.
  const [namingProject, setNamingProject] = useState<string | null>(null);
  // Only the chosen project's searches (owner, round 14). Picking one never
  // changes the Project field; changing the project clears picks it does
  // not hold.
  // The field waits for a project (owner, round 14): with none chosen, or a
  // new one not yet created, it is disabled ("Choose a project first").
  const searchesWait = projectId === "" || namingProject !== null;
  const searches = searchesWait
    ? []
    : linkableSearches(tasks.data?.data ?? []).filter((search) => search.project_ids.includes(projectId));
  const chooseProject = (next: string) => {
    setProjectId(next);
    setFromTaskIds((ids) =>
      ids.filter((id) => {
        const search = linkableSearches(tasks.data?.data ?? []).find((candidate) => candidate.task_id === id);
        return next !== "" && search !== undefined && search.project_ids.includes(next);
      }),
    );
  };
  const create = useCreateTask();
  // A name typed but not created when the task starts is made on the way.
  const makeProject = useMakeProject();
  const [projectFailed, setProjectFailed] = useState(false);
  const navigate = useNavigate();
  // A theory of change can start from the user's own diagram (task 054, increment 5).
  const [file, setFile] = useState<File | null>(null);
  const pending = create.isPending || makeProject.isPending;
  const canSend = (question.trim().length > 0 || file !== null) && !pending;
  const copy = FORM_COPY[capability];

  // Create the task and open it. `draw` goes straight to the empty canvas: the user
  // draws the theory without the Task Agent (owner, 2026-11-05). An upload opens with its file.
  const createTask = (taskProjectId: string | null, draw: boolean) => {
    const upload = draw ? null : file;
    create.mutate(
      {
        question: question.trim() !== "" ? question : upload !== null ? `My own theory of change (${upload.name})` : "My own theory of change",
        projectId: taskProjectId,
        capability,
        fromTaskIds,
      },
      {
        // A drawn theory opens on the empty canvas; an upload opens with its
        // file. Otherwise the Agent tab streams the opening turn (task 058,
        // N9): the words the person typed travel with the navigation, with
        // the turn id minted here so a repeated mount can never post it twice.
        onSuccess: (task) => {
          if (draw) void navigate(`/tasks/${task.task_id}/result`);
          else if (upload !== null)
            void navigate(`/tasks/${task.task_id}`, {
              state: { tocFile: upload, note: question.trim() } satisfies TocUploadHandOff,
            });
          else
            void navigate(`/tasks/${task.task_id}`, {
              state: { openingTurn: { message: question.trim(), clientTurnId: crypto.randomUUID() } },
            });
        },
      },
    );
  };

  const submit = (draw = false) => {
    if (draw ? pending : !canSend) return;
    // A name typed in the picker but not created yet is made first, then
    // the task in it (round 13); a blank one reads as None.
    const name = namingProject?.trim() ?? "";
    if (namingProject !== null && name !== "") {
      setProjectFailed(false);
      makeProject.make(name, {
        onSuccess: ({ projectId }) => createTask(projectId, draw),
        onError: () => setProjectFailed(true),
      });
      return;
    }
    createTask(namingProject !== null || projectId === "" ? null : projectId, draw);
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {/* No capability line above the heading: the heading names the kind of
          work (owner, round 10), and the title starts at the page's 44 px
          top padding, where the lists' titles start. */}
      <h1 className="text-display font-extrabold tracking-[-0.5px] text-navy text-pretty max-md:text-title">
        {copy.heading}
      </h1>
      <p className="whitespace-pre-line mt-3 max-w-prose text-lead font-normal leading-[25px] text-grey text-pretty max-md:text-body max-md:leading-snug">
        {copy.blurb}
      </p>

      {/* The question step, then the two optional fields, then the primary
          alone on its own row at the right, nothing below it (owner, round
          14: the page's foot was busy). */}
      <div className="mt-6 border border-line-2 bg-paper px-[18px] py-3.5 focus-within:outline-2 focus-within:outline-blue">
        <label className="sr-only" htmlFor="new-task-question">
          Your question
        </label>
        <textarea
          id="new-task-question"
          autoFocus
          rows={3}
          placeholder={copy.placeholder}
          value={question}
          onChange={(event) => {
            setQuestion(event.target.value);
            // Grow with the text, up to half the screen; then it scrolls.
            event.target.style.height = "auto";
            event.target.style.height = `${event.target.scrollHeight}px`;
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          className="block max-h-[50vh] min-h-[5.5rem] w-full resize-none overflow-y-auto border-0 bg-transparent p-0 text-lead leading-[25px] text-ink focus-visible:outline-none"
        />
        {/* A theory of change can start from the user's own diagram, or from an empty canvas. */}
        {capability === "theory_of_change" && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <AttachTheory file={file} onFile={setFile} />
            {/* Hidden while a file is attached: drawing your own would drop the file. */}
            {file === null && (
              <button
                type="button"
                onClick={() => submit(true)}
                disabled={pending}
                className={cn(LINK_CLASS, "shrink-0 text-meta leading-5")}
              >
                Start drafting yourself →
              </button>
            )}
          </div>
        )}
      </div>
      <p className="mt-2 text-meta font-normal leading-5 text-grey">
        Enter to send · Shift+Enter for a new line
      </p>

      {/* Two plain optional fields, each a label, one line of help and its
          control, 24 px apart (owner, rounds 13 and 14). The create call
          carries both: the project membership and the links land with the
          task. */}
      <div className="mt-8 max-w-md">
        <label className={FIELD_LABEL_CLASS} htmlFor="new-task-project">
          {PROJECT.one}
        </label>
        <p className={FIELD_HELP_CLASS}>Add this {TASK.lower} to a {PROJECT.lower}.</p>
        {/* None, the reader's projects, then New project… (the shared
            picker: the task menu and the Share page use the same one). */}
        <div className="mt-2">
          <ProjectPicker
            id="new-task-project"
            label={PROJECT.one}
            value={projectId}
            projects={assignableProjects}
            noneLabel="None"
            onChange={chooseProject}
            onNaming={(name) => {
              // Naming a new project clears the picks: it holds none.
              if (name !== null) setFromTaskIds([]);
              setNamingProject(name);
            }}
          />
        </div>
      </div>

      {capability === "options_scoping" && (
        <div className="mt-6 max-w-md">
          <label className={FIELD_LABEL_CLASS} htmlFor="new-task-from">
            Evidence search to start from
          </label>
          <p className={FIELD_HELP_CLASS}>
            {START_FROM_HELP}
          </p>
          {/* The searchable multi-select (owner, round 14): the reader's own
              finished searches in the chosen project; disabled until there
              is one. */}
          <MultiSelect
            id="new-task-from"
            label="Evidence search to start from"
            options={searches.map((search) => ({ value: search.task_id, label: search.name }))}
            values={searchesWait ? [] : fromTaskIds}
            onChange={setFromTaskIds}
            disabled={searchesWait}
            placeholder={searchesWait ? `Choose a ${PROJECT.lower} first` : "None"}
            filterLabel="Find a search"
            empty="No finished evidence searches"
            className="mt-2"
          />
        </div>
      )}

      {(create.isError || projectFailed) && (
        <Card role="alert" className="mt-6 max-w-md p-4 text-body text-navy">
          {projectFailed
            ? `The ${PROJECT.lower} couldn't be created. Try again.`
            : `The ${TASK.lower} couldn't be started. Try again.`}
        </Card>
      )}

      <div className="mt-8 flex justify-end">
        <Button type="submit" size="entry" disabled={!canSend}>
          {pending ? "Starting…" : copy.submitLabel}
        </Button>
      </div>
    </form>
  );
}

/** New task: choose a kind of work, then ask the question. */
export function NewTaskView() {
  useDocumentTitle(COPY.newTask);
  const [searchParams, setSearchParams] = useSearchParams();
  // The chosen capability is URL-addressable, like every other view state.
  // A key that is not one of the selectable ones — an old bookmark, a typo —
  // falls back to the picker rather than rendering a form for work the
  // server would refuse to create.
  const requested = searchParams.get("capability");
  const picked = isSelectableCapability(requested) ? requested : null;

  return (
    <main className="mx-auto flex max-w-[1180px] justify-center px-6 pt-11 pb-9 max-md:px-4 max-md:py-6">
      <div className="w-full max-w-[50vw] min-w-0 max-md:max-w-full">
        {picked !== null ? (
          <QuestionForm capability={picked} />
        ) : (
          <>
            <h1 className="text-display font-extrabold tracking-[-0.5px] text-navy text-pretty max-md:text-title">
              {COPY.newTaskPrompt}
            </h1>
            <CapabilityList
              onPick={(key) => {
                const next = new URLSearchParams(searchParams);
                next.set("capability", key);
                setSearchParams(next);
              }}
            />
          </>
        )}
      </div>
    </main>
  );
}
