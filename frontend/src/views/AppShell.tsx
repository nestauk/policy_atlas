import { useState } from "react";
import { Outlet, useLocation, useParams } from "react-router";

import { useArchiveProject, useUpdateProject } from "../api/mutations";
import { useCheckIns, useProject } from "../api/queries";
import { useAuth } from "../auth";
import { TitleMarkerProvider } from "../lib/title";
import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { StatusDot } from "../ui/brand/Card";
import { NavBar, NavItem, NavLogo } from "../ui/brand/Nav";
import { ErrorBoundary } from "../ui/feedback/ErrorBoundary";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { ToastProvider, useToast } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";

/** Project settings affordance (028 F.5): rename + archive, wired to the
 *  existing project mutations — the LandingView.tsx ProjectCard pattern,
 *  condensed into the header popover. Rename saves inline; archive takes an
 *  explicit confirm step before the mutation fires. */
function ProjectSettingsMenu({ projectId, projectName }: { projectId: string; projectName: string }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmingArchive, setConfirmingArchive] = useState(false);
  const [draftName, setDraftName] = useState(projectName);
  const update = useUpdateProject(projectId);
  const archive = useArchiveProject(projectId);
  const toast = useToast();

  const reset = () => {
    setEditing(false);
    setConfirmingArchive(false);
    setDraftName(projectName);
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
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Project settings"
          title="Project settings"
          className="cursor-pointer text-grey hover:text-navy focus-visible:outline-2 focus-visible:outline-blue"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-4 w-4"
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
      <PopoverContent align="start" className="w-72 space-y-3">
        {editing ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              saveRename();
            }}
          >
            <label className="sr-only" htmlFor="project-settings-name">
              Project name
            </label>
            <input
              id="project-settings-name"
              autoFocus
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") reset();
              }}
              className="w-full border border-line-2 bg-paper px-2 py-1.5 text-meta font-bold text-navy focus-visible:outline-2 focus-visible:outline-blue"
            />
            {update.isError && (
              <p role="alert" className="mt-2 text-caption text-red">
                The project couldn't be renamed. Try again.
              </p>
            )}
            <div className="mt-3 flex gap-2">
              <Button type="submit" size="sm" disabled={!draftName.trim() || update.isPending}>
                Save name
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={reset}>
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <>
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="block w-full cursor-pointer text-left text-meta font-semibold text-navy hover:text-blue"
            >
              Rename
            </button>
            {archive.isError && (
              <p role="alert" className="text-caption text-red">
                The project couldn't be archived. Try again.
              </p>
            )}
            {confirmingArchive ? (
              <div className="space-y-2 text-caption text-grey">
                <p>Archiving removes this project from your active projects.</p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={archive.isPending}
                    onClick={() =>
                      archive.mutate(undefined, {
                        onSuccess: () => setOpen(false),
                        onError: () =>
                          toast.toast({
                            title: "Archive failed",
                            description: "The project couldn't be archived. Try again.",
                            tone: "error",
                          }),
                      })
                    }
                  >
                    Confirm archive
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirmingArchive(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmingArchive(true)}
                className="block w-full cursor-pointer text-left text-meta font-semibold text-navy hover:text-blue"
              >
                Archive
              </button>
            )}
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}

/** App chrome: brand group left, project-scoped nav right (growing underline). */
export function AppShell() {
  const { projectId } = useParams();
  const location = useLocation();
  const auth = useAuth();
  const project = useProject(projectId ?? "");
  const base = projectId === undefined ? null : `/projects/${projectId}`;
  const inWorkspace = base !== null && location.pathname === base;

  // Pending check-in visibility outside the workspace (contract strand 14):
  // poll cheaply for a pending check-in only while the user isn't already on
  // the workspace view (where the check-in card itself is the live source of
  // truth) — the nav badge and title marker exist precisely to be seen from
  // everywhere else.
  const pendingCheckIns = useCheckIns(projectId ?? "", "pending", {
    enabled: base !== null && !inWorkspace,
    refetchInterval: 15_000,
  });
  const hasPendingCheckIn = base !== null && !inWorkspace && (pendingCheckIns.data?.data.length ?? 0) > 0;

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <TitleMarkerProvider active={hasPendingCheckIn}>
          <div className="min-h-svh">
            <NavBar>
              <div className="flex min-w-0 items-center gap-3">
                <NavItem to="/">
                  <NavLogo />
                </NavItem>
                {project.data !== undefined && (
                  <span className="flex min-w-0 items-center gap-2 text-meta text-grey">
                    <span aria-hidden="true" className="text-line-2">
                      /
                    </span>
                    <span className="truncate font-semibold text-navy">{scrub(project.data.name)}</span>
                    <ProjectSettingsMenu projectId={project.data.project_id} projectName={project.data.name} />
                  </span>
                )}
              </div>
              <div className="flex items-center gap-5">
                {base !== null && (
                  <>
                    <NavItem to={base}>
                      <span className="inline-flex items-center gap-1.5">
                        Workspace
                        {hasPendingCheckIn && (
                          <>
                            <StatusDot tone="paused" />
                            <span className="sr-only">Check-in pending</span>
                          </>
                        )}
                      </span>
                    </NavItem>
                    <NavItem to={`${base}/evidence-base`}>Evidence base</NavItem>
                    <NavItem to={`${base}/findings`}>Findings</NavItem>
                    <NavItem to={`${base}/sources`}>Sources</NavItem>
                    <NavItem to={`${base}/landscape`}>Landscape</NavItem>
                    <NavItem to={`${base}/decisions`}>Decision log</NavItem>
                  </>
                )}
                {/* 026 live-check gap: the AuthApi always had signOut; nothing
                    rendered it — Cognito users had no way out of a session. */}
                {auth.user !== null && (
                  <span className="flex items-center gap-3">
                    <span className="text-caption text-grey">{scrub(auth.user.sub)}</span>
                    <button
                      type="button"
                      onClick={() => auth.signOut()}
                      className="cursor-pointer text-meta text-grey hover:text-navy"
                    >
                      Sign out
                    </button>
                  </span>
                )}
              </div>
            </NavBar>
            {/* Cross-tab pause banner (028 strand 14 — pause salience): a
                paused run must be unmissable from every tab; the banner jumps
                straight to the waiting check-in. */}
            {hasPendingCheckIn && base !== null && (
              <div role="status" className="border-b border-orange bg-orange/10 px-5 py-2">
                <NavItem to={base}>
                  <span className="text-meta font-semibold text-navy">
                    The analysis is paused — a check-in is waiting on you. Go to the check-in →
                  </span>
                </NavItem>
              </div>
            )}
            <ErrorBoundary key={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </TitleMarkerProvider>
      </TooltipProvider>
    </ToastProvider>
  );
}
