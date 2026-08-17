import { useState } from "react";
import { Outlet, useLocation, useParams } from "react-router";

import { useArchiveProject, useUpdateProject } from "../api/mutations";
import { useCheckIns, useProject } from "../api/queries";
import { useAuth } from "../auth";
import { TitleMarkerProvider } from "../lib/title";
import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { StatusDot } from "../ui/brand/Card";
import { LifecycleBar } from "../ui/brand/LifecycleBar";
import { NavBar, NavItem, NavLogo } from "../ui/brand/Nav";
import { COPY } from "../lib/vocabulary";
import { lifecycleTabs } from "./lifecycle";
import { ErrorBoundary } from "../ui/feedback/ErrorBoundary";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { ChatSidePanel } from "./workspace/chat/ChatSidePanel";
import { ToastProvider, useToast } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";

/** Project settings affordance (028 F.5): rename + archive, wired to the
 *  existing project mutations — the project-card pattern,
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
  // Locking reads `latest_run.status`, so the shell needs it fresh while a run
  // moves. The run stream already invalidates this query on the two pages that
  // mount it (Plan and Results), so polling only has to cover the pages that
  // don't — the same shape as the pending check-in poll below. Mounting a
  // third `useRunStream` here would double-connect on those two pages.
  const project = useProject(projectId ?? "", { pollWhileRunning: true });
  const base = projectId === undefined ? null : `/projects/${projectId}`;
  const inWorkspace = base !== null && location.pathname === base;
  const showChatPanel = base !== null && !inWorkspace;
  // With a chat open beside the view, the two columns scroll independently —
  // the workspace's own two-pane behaviour (fixed viewport height, each
  // column owns its scroll). Closed, the page keeps its normal scroll.
  // `.get`, not `.has`: `?chat=` (present but empty) must read as closed,
  // matching `useActiveConversation`'s own non-empty check — otherwise a
  // bare `?chat=` opens a panel bound to conversation id "".
  const chatOpen = showChatPanel && Boolean(new URLSearchParams(location.search).get("chat"));

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
                  <LifecycleBar
                    hint={COPY.lockedHint}
                    items={lifecycleTabs(base, project.data?.latest_run?.status).map((item) =>
                      item.tab === "plan" && hasPendingCheckIn
                        ? {
                            ...item,
                            marker: (
                              <>
                                <StatusDot tone="paused" />
                                <span className="sr-only">Check-in pending</span>
                              </>
                            ),
                          }
                        : item,
                    )}
                  />
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
            {/* Chat beside every project view outside the workspace (029
                rev 3.4): the workspace already hosts the full conversation
                rail, so the panel mounts everywhere else in the project. */}
            <div className={chatOpen ? "flex min-w-0 lg:h-[calc(100svh-58px)]" : "flex min-w-0"}>
              {/* Chat on the LEFT — parity with the workspace rail. Its own
                  boundary: a render error in the chat subtree must not take
                  out the rest of the shell (nav, the routed view). */}
              {showChatPanel && (
                <ErrorBoundary key={projectId}>
                  <ChatSidePanel projectId={projectId ?? ""} />
                </ErrorBoundary>
              )}
              <div className={chatOpen ? "min-w-0 flex-1 lg:overflow-y-auto" : "min-w-0 flex-1"}>
                <ErrorBoundary key={location.pathname}>
                  <Outlet />
                </ErrorBoundary>
              </div>
            </div>
          </div>
        </TitleMarkerProvider>
      </TooltipProvider>
    </ToastProvider>
  );
}
