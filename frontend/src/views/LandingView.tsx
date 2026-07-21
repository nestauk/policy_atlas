import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useCreateProject } from "../api/mutations";
import { useProjects } from "../api/queries";
import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { Card, StatusDot } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";

type LatestRun = { status: string } | null | undefined;

/** Derive the card's presentation from the latest capability run — run state
 * is never cached on the project row (read model, contract strand 3). */
function runPresentation(latestRun: LatestRun): {
  dot: "running" | "complete" | "paused" | "idle" | "failed";
  label: string;
  tone: "default" | "blue" | "soft" | "green" | "yellow" | "red";
} {
  switch (latestRun?.status) {
    case "running":
      return { dot: "running", label: "Analysing the evidence…", tone: "yellow" };
    case "paused":
      return { dot: "paused", label: "Paused — waiting on your input", tone: "yellow" };
    case "succeeded":
      return { dot: "complete", label: "Complete", tone: "green" };
    case "degraded":
      return { dot: "complete", label: "Complete — with gaps", tone: "yellow" };
    case "failed":
      return { dot: "failed", label: "Failed", tone: "red" };
    case "interrupted":
      return { dot: "failed", label: "Interrupted", tone: "red" };
    case "aborted":
      return { dot: "idle", label: "Stopped", tone: "soft" };
    default:
      return { dot: "idle", label: "Not started", tone: "soft" };
  }
}

function NewProjectForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const create = useCreateProject();
  const navigate = useNavigate();
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        const trimmed = name.trim();
        if (trimmed.length === 0) return;
        create.mutate(
          { name: trimmed },
          {
            onSuccess: (project) => {
              onDone();
              void navigate(`/projects/${project.project_id}`);
            },
          },
        );
      }}
    >
      <label className="text-[13px] font-semibold text-navy" htmlFor="new-project-name">
        Project name
      </label>
      <input
        id="new-project-name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="e.g. Childhood obesity — what works"
        className="border border-line-2 bg-paper px-3 py-2.5 text-[13px] focus-visible:outline-2 focus-visible:outline-blue"
      />
      {create.isError && (
        <p role="alert" className="text-xs text-red">
          The project couldn't be created. Try again.
        </p>
      )}
      <div className="flex items-center gap-2">
        <Button type="submit" disabled={create.isPending || name.trim().length === 0}>
          Create project
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** Landing: project cards with run-derived presentation, honest states. */
export function LandingView() {
  const projects = useProjects();
  const [creating, setCreating] = useState(false);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8 flex items-end justify-between gap-6">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-[-0.5px] text-navy">
            Your evidence projects
          </h1>
          <p className="mt-1.5 max-w-xl text-[13px] text-grey">
            Each project turns one policy question into an evidence base you can read,
            steer and cite.
          </p>
        </div>
        {!creating && <Button onClick={() => setCreating(true)}>New project</Button>}
      </header>

      {creating && (
        <Card className="mb-8 max-w-md p-5">
          <NewProjectForm onDone={() => setCreating(false)} />
        </Card>
      )}

      {projects.isPending && (
        <div
          aria-busy="true"
          aria-label="Loading projects"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-36 animate-pulse border border-line bg-paper-2" />
          ))}
        </div>
      )}

      {projects.isError && (
        <Card role="alert" className="max-w-md p-5 text-[13px] text-navy">
          Projects couldn't be loaded.{" "}
          <button
            type="button"
            className="cursor-pointer font-bold text-blue hover:underline"
            onClick={() => void projects.refetch()}
          >
            Retry
          </button>
        </Card>
      )}

      {projects.data !== undefined && projects.data.data.length === 0 && !creating && (
        <Card role="status" className="mx-auto max-w-md p-8 text-center">
          <h2 className="font-display text-lg font-bold text-navy">No projects yet</h2>
          <p className="mt-1.5 text-[13px] text-grey">
            Start with the policy question you need evidence for.
          </p>
          <Button className="mt-4" onClick={() => setCreating(true)}>
            New project
          </Button>
        </Card>
      )}

      {projects.data !== undefined && projects.data.data.length > 0 && (
        <ul role="list" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data.data.map((project) => {
            const presentation = runPresentation(project.latest_run);
            return (
              <li key={project.project_id}>
                <Link
                  to={`/projects/${project.project_id}`}
                  className="block h-full no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
                >
                  <Card className="flex h-full flex-col gap-3 p-5 transition-shadow hover:shadow-[0_2px_6px_rgba(15,41,74,0.08),0_12px_32px_rgba(15,41,74,0.08)]">
                    <h2 className="font-display text-[15px] font-bold leading-snug text-navy">
                      {scrub(project.name)}
                    </h2>
                    {project.question !== null && project.question !== undefined && (
                      <p className="line-clamp-2 text-[12.5px] leading-relaxed text-grey">
                        {scrub(project.question)}
                      </p>
                    )}
                    <div className="mt-auto flex items-center gap-2 pt-1">
                      <Chip tone={presentation.tone}>
                        <StatusDot tone={presentation.dot} />
                        {presentation.label}
                      </Chip>
                    </div>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
