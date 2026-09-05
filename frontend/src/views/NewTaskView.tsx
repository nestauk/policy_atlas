import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { useProjects } from "../api/queries";
import { useCreateTask } from "../api/mutations";
import { CAPABILITIES } from "../lib/capabilities";
import { useDocumentTitle } from "../lib/title";
import { COPY, PROJECT, TASK } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import { cn } from "../ui/brand/cn";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";

/** Step one: pick a kind of work. Only one of the four can run. */
function CapabilityList({ onPick }: { onPick: () => void }) {
  return (
    <ul role="list" className="mt-10 flex flex-col">
      {CAPABILITIES.map((capability) =>
        capability.available ? (
          <li key={capability.key}>
            <button
              type="button"
              onClick={onPick}
              className="flex w-full cursor-pointer items-center justify-between gap-4 border-b border-line px-0.5 py-3.5 text-left text-lead font-normal leading-[25px] text-navy hover:text-blue focus-visible:outline-2 focus-visible:outline-blue"
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
              <span className="text-lead font-normal leading-[25px] text-grey">{capability.name}</span>
              <span className="shrink-0 text-caption font-semibold uppercase tracking-[0.06em] text-grey">
                {COPY.comingSoon}
              </span>
            </div>
          </li>
        ),
      )}
    </ul>
  );
}

type ProjectOption = { project_id: string; name: string };

/** Project picker — Popover menu styled like the app chrome, not a native select. */
function ProjectPicker({
  id,
  value,
  options,
  onChange,
}: {
  id: string;
  value: string;
  options: readonly ProjectOption[];
  onChange: (projectId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find((project) => project.project_id === value);
  const label = selected?.name ?? COPY.noProject;

  const pick = (projectId: string) => {
    onChange(projectId);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          aria-haspopup="listbox"
          aria-expanded={open}
          className="inline-flex min-w-[14rem] cursor-pointer items-center justify-between gap-3 border border-line-2 bg-paper px-3 py-2 text-body font-normal text-navy hover:border-navy focus-visible:outline-2 focus-visible:outline-blue"
        >
          <span className="truncate">{label}</span>
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-4 w-4 shrink-0 text-grey"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-1">
        <ul role="listbox" aria-labelledby={id} className="flex flex-col">
          <li role="none">
            <button
              type="button"
              role="option"
              aria-selected={value === ""}
              onClick={() => pick("")}
              className={cn(
                "block w-full cursor-pointer px-3 py-2 text-left text-body font-normal text-navy hover:bg-blue-tint-2 hover:text-blue",
                value === "" && "bg-blue-tint-2 font-medium",
              )}
            >
              {COPY.noProject}
            </button>
          </li>
          {options.map((project) => (
            <li key={project.project_id} role="none">
              <button
                type="button"
                role="option"
                aria-selected={value === project.project_id}
                onClick={() => pick(project.project_id)}
                className={cn(
                  "block w-full cursor-pointer px-3 py-2 text-left text-body font-normal text-navy hover:bg-blue-tint-2 hover:text-blue",
                  value === project.project_id && "bg-blue-tint-2 font-medium",
                )}
              >
                {project.name}
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

/** Step two: the question, and as little else as possible beside it. */
function QuestionForm() {
  const [searchParams] = useSearchParams();
  const presetProject = searchParams.get("project") ?? "";
  const [question, setQuestion] = useState("");
  const [projectId, setProjectId] = useState(presetProject);
  const projects = useProjects();
  // Every task this caller can read is a valid target: assignment
  // resolves under the colleague-mutation grade (owner ruling 2026-08-27),
  // so a colleague may add their task to an org-visible task they did
  // not create. The listing is already scoped to what the caller may read.
  const assignableProjects = projects.data?.data ?? [];
  const create = useCreateTask();
  const navigate = useNavigate();
  const canSend = question.trim().length > 0 && !create.isPending;

  const submit = () => {
    if (!canSend) return;
    create.mutate(
      { question, projectId: projectId === "" ? null : projectId },
      { onSuccess: (task) => void navigate(`/tasks/${task.task_id}`) },
    );
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <p className="text-body font-semibold uppercase tracking-[0.06em] text-grey">
        Evidence search
      </p>
      <h1 className="mt-2 text-display font-extrabold tracking-[-0.5px] text-navy text-pretty">
        What do you need evidence on?
      </h1>
      <p className="mt-3 max-w-prose text-lead font-normal leading-[25px] text-grey text-pretty">
      Ask a policy question. Policy Atlas will clarify what you need, draft a search plan for your review, then find the evidence.
      </p>

      <div className="mt-6 flex items-end gap-3 border border-line-2 bg-paper px-[18px] py-3.5 focus-within:outline-2 focus-within:outline-blue">
        <label className="sr-only" htmlFor="new-task-question">
          Your question
        </label>
        <textarea
          id="new-task-question"
          autoFocus
          rows={3}
          placeholder="e.g. What works to reduce childhood obesity in the UK?"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          className="min-h-[5.5rem] min-w-0 flex-1 resize-none border-0 bg-transparent p-0 text-lead leading-[25px] text-ink focus-visible:outline-none"
        />
        <Button
          type="submit"
          size="md"
          disabled={!canSend}
          className="shrink-0 px-6 py-3.5 text-body"
        >
          {create.isPending ? "Starting…" : "Start"}
        </Button>
      </div>
      <p className="mt-2 text-meta font-normal leading-5 text-grey">
        Enter to send · Shift+Enter for a new line
      </p>

      {assignableProjects.length > 0 && (
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <label className="text-meta font-normal text-grey" htmlFor="new-task-project">
            Add to a {PROJECT.lower}
          </label>
          <ProjectPicker
            id="new-task-project"
            value={projectId}
            options={assignableProjects}
            onChange={setProjectId}
          />
        </div>
      )}

      {create.isError && (
        <Card role="alert" className="mt-6 max-w-md p-4 text-body text-navy">
          The {TASK.lower} couldn't be started. Try again.
        </Card>
      )}
    </form>
  );
}

/** New task: choose a kind of work, then ask the question. */
export function NewTaskView() {
  useDocumentTitle(COPY.newTask);
  const [searchParams, setSearchParams] = useSearchParams();
  // The chosen capability is URL-addressable, like every other view state.
  const picked = searchParams.get("capability") === "evidence_search";

  return (
    <main className="mx-auto flex max-w-[1180px] justify-center px-6 py-9">
      <div className="w-full max-w-[50vw] min-w-0">
        {picked ? (
          <QuestionForm />
        ) : (
          <>
            <p className="text-body font-semibold uppercase tracking-[0.06em] text-grey">
              {COPY.newTask}
            </p>
            <h1 className="mt-2 text-display font-extrabold tracking-[-0.5px] text-navy text-pretty">
              {COPY.newTaskPrompt}
            </h1>
            <CapabilityList
              onPick={() => {
                const next = new URLSearchParams(searchParams);
                next.set("capability", "evidence_search");
                setSearchParams(next);
              }}
            />
          </>
        )}
      </div>
    </main>
  );
}
