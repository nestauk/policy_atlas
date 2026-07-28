import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useArchiveProject, useCreateProject, useUpdateProject } from "../api/mutations";
import { useProjects } from "../api/queries";
import type { components } from "../api/gen/types";
import { scrub } from "../lib/scrub";
import { useDocumentTitle } from "../lib/title";
import { Button } from "../ui/brand/Button";
import { Card, StatusDot } from "../ui/brand/Card";
import { Chip } from "../ui/brand/Chip";
import { useToast } from "../ui/radix/Toast";
import { cancelledRenameState } from "./landingPresentation";

type LatestRun = { status: string } | null | undefined;
type Project = components["schemas"]["ProjectOut"];

/** Derive the card's presentation from the latest capability run — run state
 * is never cached on the project row (read model, contract strand 3). */
function runPresentation(latestRun: LatestRun): {
  dot: "running" | "complete" | "paused" | "idle" | "failed";
  label: string;
  tone: "default" | "blue" | "soft" | "green" | "yellow" | "red";
} {
  switch (latestRun?.status) {
    case "running": return { dot: "running", label: "Analysing the evidence…", tone: "yellow" };
    case "paused": return { dot: "paused", label: "Paused — waiting on your input", tone: "yellow" };
    case "succeeded": return { dot: "complete", label: "Complete", tone: "green" };
    case "degraded": return { dot: "complete", label: "Complete — with gaps", tone: "yellow" };
    case "failed": return { dot: "failed", label: "Failed", tone: "red" };
    case "interrupted": return { dot: "failed", label: "Interrupted", tone: "red" };
    case "aborted": return { dot: "idle", label: "Stopped", tone: "soft" };
    default: return { dot: "idle", label: "Not started", tone: "soft" };
  }
}

function NewProjectForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const create = useCreateProject();
  const navigate = useNavigate();
  return (
    <form className="flex flex-col gap-3" onSubmit={(event) => {
      event.preventDefault();
      const trimmed = name.trim();
      if (!trimmed) return;
      create.mutate({ name: trimmed }, { onSuccess: (project) => { onDone(); void navigate(`/projects/${project.project_id}`); } });
    }}>
      <label className="text-[13px] font-semibold text-navy" htmlFor="new-project-name">Project name</label>
      <input id="new-project-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Childhood obesity — what works" className="border border-line-2 bg-paper px-3 py-2.5 text-[13px] focus-visible:outline-2 focus-visible:outline-blue" />
      {create.isError && <p role="alert" className="text-xs text-red">The project couldn't be created. Try again.</p>}
      <div className="flex items-center gap-2"><Button type="submit" disabled={create.isPending || !name.trim()}>Create project</Button><Button variant="ghost" onClick={onDone}>Cancel</Button></div>
    </form>
  );
}

/** Landing: project cards expose rename/archive actions beside run-derived presentation. */
export function LandingView() {
  useDocumentTitle("Projects");
  const projects = useProjects();
  const [creating, setCreating] = useState(false);
  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8 flex items-end justify-between gap-6">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-[-0.5px] text-navy">Your evidence projects</h1>
          <p className="mt-1.5 max-w-xl text-[13px] text-grey">Each project turns one policy question into an evidence base you can read, steer and cite.</p>
        </div>
        {!creating && <Button onClick={() => setCreating(true)}>New project</Button>}
      </header>
      {creating && <Card className="mb-8 max-w-md p-5"><NewProjectForm onDone={() => setCreating(false)} /></Card>}
      {projects.isPending && <ProjectLoading />}
      {projects.isError && <Card role="alert" className="max-w-md p-5 text-[13px] text-navy">Projects couldn't be loaded. <button type="button" className="cursor-pointer font-bold text-blue hover:underline" onClick={() => void projects.refetch()}>Retry</button></Card>}
      {projects.data !== undefined && projects.data.data.length === 0 && !creating && (
        <Card role="status" className="mx-auto max-w-md p-8 text-center"><h2 className="font-display text-lg font-bold text-navy">No projects yet</h2><p className="mt-1.5 text-[13px] text-grey">Start with the policy question you need evidence for.</p><Button className="mt-4" onClick={() => setCreating(true)}>New project</Button></Card>
      )}
      {projects.data !== undefined && projects.data.data.length > 0 && (
        <ul role="list" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data.data.map((project, index) => <ProjectCard key={project.project_id} project={project} delayMs={Math.min(index, 8) * 60} />)}
          <li>
            <button type="button" onClick={() => setCreating(true)} className="flex min-h-40 w-full cursor-pointer items-center justify-center border border-dashed border-line-2 bg-paper text-[13px] font-semibold text-grey hover:border-navy hover:text-navy focus-visible:outline-2 focus-visible:outline-blue">+ New project</button>
          </li>
        </ul>
      )}
    </main>
  );
}

function ProjectLoading() {
  return <div aria-busy="true" aria-label="Loading projects" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 3 }).map((_, index) => <div key={index} className="h-36 animate-pulse border border-line bg-paper-2" />)}</div>;
}

function ProjectCard({ project, delayMs }: { project: Project; delayMs: number }) {
  const [editing, setEditing] = useState(false);
  const [confirmingArchive, setConfirmingArchive] = useState(false);
  const [draftName, setDraftName] = useState(project.name);
  const update = useUpdateProject(project.project_id);
  const archive = useArchiveProject(project.project_id);
  const toast = useToast();
  const presentation = runPresentation(project.latest_run);
  const cancelRename = () => {
    const reset = cancelledRenameState(project.name);
    setDraftName(reset.draftName);
    setEditing(reset.editing);
  };
  const saveRename = () => {
    const name = draftName.trim();
    if (!name) return;
    update.mutate(
      { name },
      {
        onSuccess: () => setEditing(false),
        onError: () =>
          toast.toast({
            title: "Rename failed",
            description: "The project couldn't be renamed. Try again.",
            tone: "error",
          }),
      },
    );
  };
  return (
    <li className="anim-rise" style={{ animationDelay: `${delayMs}ms` }}>
      <Card className="relative flex min-h-40 h-full flex-col gap-3 p-5">
        {editing ? (
          <form onSubmit={(event) => { event.preventDefault(); saveRename(); }}>
            <label className="sr-only" htmlFor={`project-name-${project.project_id}`}>Project name</label>
            <input id={`project-name-${project.project_id}`} autoFocus value={draftName} onChange={(event) => setDraftName(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") cancelRename(); }} className="w-full border border-line-2 bg-paper px-2 py-1.5 text-[14px] font-bold text-navy focus-visible:outline-2 focus-visible:outline-blue" />
            {update.isError && <p role="alert" className="mt-2 text-xs text-red">The project couldn't be renamed. Try again.</p>}
            <div className="mt-3 flex gap-2"><Button type="submit" size="sm" disabled={!draftName.trim() || update.isPending}>Save name</Button><Button type="button" variant="ghost" size="sm" onClick={cancelRename}>Cancel rename</Button></div>
          </form>
        ) : (
          <>
            <div className="absolute right-3 top-3 flex gap-1">
              <Button size="sm" variant="ghost" onClick={() => { setDraftName(project.name); setEditing(true); }}>Rename project</Button>
              <Button
                size="sm"
                variant={confirmingArchive ? "primary" : "ghost"}
                onClick={() => {
                  if (confirmingArchive) {
                    archive.mutate(undefined, {
                      onError: () =>
                        toast.toast({
                          title: "Archive failed",
                          description: "The project couldn't be archived. Try again.",
                          tone: "error",
                        }),
                    });
                  } else {
                    setConfirmingArchive(true);
                  }
                }}
                disabled={archive.isPending}
              >
                {confirmingArchive ? "Confirm archive" : "Archive project"}
              </Button>
            </div>
            {archive.isError && <p role="alert" className="pr-36 text-xs text-red">The project couldn't be archived. Try again.</p>}
            <Link to={`/projects/${project.project_id}`} className="block pr-36 no-underline focus-visible:outline-2 focus-visible:outline-blue">
              <h2 className="font-display text-[15px] font-bold leading-snug text-navy">{scrub(project.name)}</h2>
              {project.question && <p className="mt-1.5 line-clamp-2 text-[12.5px] leading-relaxed text-grey">{scrub(project.question)}</p>}
            </Link>
            {confirmingArchive && <div className="flex items-center justify-between gap-3 text-[11.5px] text-grey"><p>Archiving removes this project from your active projects. Confirm to archive it.</p><Button size="sm" variant="ghost" onClick={() => setConfirmingArchive(false)}>Cancel archive</Button></div>}
            <div className="mt-auto flex items-center gap-2 pt-1"><Chip tone={presentation.tone}><StatusDot tone={presentation.dot} />{presentation.label}</Chip></div>
          </>
        )}
      </Card>
    </li>
  );
}
