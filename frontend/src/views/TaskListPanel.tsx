import { useState } from "react";
import { Link, useNavigate } from "react-router";

import type { components } from "../api/gen/types";
import { scrub } from "../lib/scrub";
import { COPY, TASK } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";
import { taskDestination } from "./lifecycle";
import { listNewButtonClass } from "./listPageChrome";
import { TaskListRow } from "./TaskListRow";

type LatestRun = components["schemas"]["TaskOut"]["latest_run"];

export type TaskListItem = {
  task_id: string;
  name: string;
  updated_at: string;
  latest_run?: LatestRun;
  project_id?: string | null;
  source_count?: number | null;
};

function FindTask({
  rows,
  projectNames,
  showTaskPrefix,
  onClose,
}: {
  rows: readonly TaskListItem[];
  projectNames?: ReadonlyMap<string, string>;
  showTaskPrefix?: boolean;
  onClose: () => void;
}) {
  const [term, setTerm] = useState("");
  const navigate = useNavigate();
  const needle = term.trim().toLowerCase();
  const matches =
    needle === ""
      ? rows
      : rows.filter((row) => {
          const project =
            showTaskPrefix && row.project_id != null
              ? (projectNames?.get(row.project_id) ?? "")
              : "";
          const haystack = `${project} ${row.name}`.toLowerCase();
          return haystack.includes(needle);
        });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={COPY.findTask}
      className="fixed inset-x-0 top-24 z-30 mx-auto max-w-xl border border-line bg-paper p-4 shadow-lg"
    >
      <div className="flex items-center gap-3">
        <label className="sr-only" htmlFor="find-task">
          {COPY.findTask}
        </label>
        <input
          id="find-task"
          autoFocus
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") onClose();
          }}
          placeholder={`Search ${TASK.lowerMany} by name`}
          className="flex-1 border border-line-2 bg-paper px-3 py-2 text-body text-navy focus-visible:outline-2 focus-visible:outline-blue"
        />
        <button
          type="button"
          aria-label="Close search"
          onClick={onClose}
          className="cursor-pointer text-heading leading-none text-grey hover:text-navy"
        >
          ×
        </button>
      </div>
      <ul role="list" className="mt-3 max-h-80 overflow-y-auto">
        {matches.length === 0 && (
          <li className="px-1 py-3 text-body text-grey">Nothing matches “{scrub(term)}”.</li>
        )}
        {matches.map((row) => {
          const projectName =
            showTaskPrefix && row.project_id != null
              ? (projectNames?.get(row.project_id) ?? null)
              : null;
          const label =
            projectName != null ? `${projectName} / ${row.name}` : row.name;
          return (
            <li key={row.task_id}>
              <button
                type="button"
                onClick={() => {
                  onClose();
                  void navigate(taskDestination(row.task_id, row.latest_run?.status));
                }}
                className="w-full cursor-pointer border-b border-line px-1 py-2.5 text-left text-body text-navy last:border-b-0 hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-blue"
              >
                {scrub(label)}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Find-a-task and New-task controls shared by Tasks and task-detail headers. */
export function TaskListActions({
  rows,
  projectNames,
  showTaskPrefix = false,
  newTaskHref,
}: {
  rows: readonly TaskListItem[];
  projectNames?: ReadonlyMap<string, string>;
  showTaskPrefix?: boolean;
  newTaskHref: string;
}) {
  const [finding, setFinding] = useState(false);

  return (
    <>
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          className="px-3 py-2.5 text-lead font-normal"
          onClick={() => setFinding(true)}
        >
          {COPY.findTask}
        </Button>
        <Link to={newTaskHref} className={listNewButtonClass}>
          {COPY.newTask}
        </Link>
      </div>
      {finding && (
        <FindTask
          rows={rows}
          projectNames={projectNames}
          showTaskPrefix={showTaskPrefix}
          onClose={() => setFinding(false)}
        />
      )}
    </>
  );
}

type TaskListPanelProps = {
  rows: readonly TaskListItem[];
  projectNames?: ReadonlyMap<string, string>;
  showTaskPrefix?: boolean;
  isPending?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  loaded?: boolean;
};

/** Shared task list body: loading, empty, and rows. */
export function TaskListPanel({
  rows,
  projectNames,
  showTaskPrefix = false,
  isPending = false,
  isError = false,
  onRetry,
  loaded = true,
}: TaskListPanelProps) {
  if (isPending) {
    return (
      <div aria-busy="true" aria-label={`Loading ${TASK.lowerMany}`} className="space-y-2">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-14 animate-pulse border border-line bg-paper-2" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <Card role="alert" className="max-w-md p-5 text-body text-navy">
        Your {TASK.lowerMany} couldn't be loaded.{" "}
        <button
          type="button"
          className="cursor-pointer font-bold text-blue hover:underline"
          onClick={() => onRetry?.()}
        >
          Retry
        </button>
      </Card>
    );
  }

  if (loaded && rows.length === 0) return null;

  if (rows.length === 0) return null;

  return (
    <ul role="list" className="border border-line-2 bg-paper">
      {rows.map((row) => (
        <li key={row.task_id} className="border-b border-line last:border-b-0">
          <TaskListRow
            to={taskDestination(row.task_id, row.latest_run?.status)}
            name={row.name}
            projectName={
              showTaskPrefix && row.project_id != null
                ? (projectNames?.get(row.project_id) ?? null)
                : null
            }
            showTaskPrefix={showTaskPrefix}
            sourceCount={row.source_count}
            updatedAt={row.updated_at}
            latestRun={row.latest_run}
          />
        </li>
      ))}
    </ul>
  );
}
