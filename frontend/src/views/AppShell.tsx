import { useLayoutEffect, useState } from "react";
import { Outlet, useLocation, useParams } from "react-router";

import { useArchiveProject, useUpdateProject } from "../api/mutations";
import { useCheckIns, useProject } from "../api/queries";
import { useAuth } from "../auth";
import { TitleMarkerProvider } from "../lib/title";
import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { StatusDot } from "../ui/brand/Card";
import { cn } from "../ui/brand/cn";
import { LifecycleBar } from "../ui/brand/LifecycleBar";
import { NavBar, NavHomeLink, NavItem } from "../ui/brand/Nav";
import { COPY, PROJECT, TASK } from "../lib/vocabulary";
import { lifecycleTabs } from "./lifecycle";
import { ErrorBoundary } from "../ui/feedback/ErrorBoundary";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { AppFooter } from "./AppFooter";
import { SensitiveInfoBanner } from "./SensitiveInfoBanner";
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
              <p role="alert" className="mt-2 text-body text-red">
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
              <p role="alert" className="text-body text-red">
                The project couldn't be archived. Try again.
              </p>
            )}
            {confirmingArchive ? (
              <div className="space-y-2 text-body text-grey">
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

/** Account menu: a user icon in the global bar, Sign out inside the popover. */
function AccountMenu({ signOut }: { signOut: () => void }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Account"
          title="Account"
          className="flex h-8 w-8 cursor-pointer items-center justify-center text-navy hover:text-blue focus-visible:outline-2 focus-visible:outline-blue"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-6 w-6"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.75}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-44 p-1">
        <button
          type="button"
          onClick={() => signOut()}
          className="block w-full cursor-pointer px-3 py-2 text-left text-meta font-semibold text-navy hover:bg-blue-tint-2 hover:text-blue"
        >
          Sign out
        </button>
      </PopoverContent>
    </Popover>
  );
}

/** App chrome: global controls always; task stages on a second bar. */
export function AppShell() {
  const { projectId } = useParams();
  const location = useLocation();
  const auth = useAuth();
  // The run stream already invalidates this query on the pages that
  // mount it (Plan, Results, Sources), so polling only has to cover the
  // pages that don't — the same shape as the pending check-in poll below.
  // Mounting `useRunStream` here would double-connect on those pages.
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

  // Task views lock to the viewport so the app/lifecycle chrome stays put
  // and only the panes below scroll. List pages keep normal document scroll.
  useLayoutEffect(() => {
    if (base === null) return undefined;
    document.documentElement.classList.add("overflow-hidden");
    return () => document.documentElement.classList.remove("overflow-hidden");
  }, [base]);

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <TitleMarkerProvider active={hasPendingCheckIn}>
          <div
            className={cn(
              "flex w-full min-w-0 max-w-full flex-col",
              base === null ? "min-h-svh" : "h-svh overflow-hidden",
            )}
          >
            <NavBar aria-label="App" className="shrink-0">
              <NavHomeLink />
              <div className="flex items-center gap-5">
                <NavItem to="/new" end>
                  {COPY.navNew}
                </NavItem>
                <NavItem
                  to="/"
                  match={(path) => path === "/" || path.startsWith("/projects/")}
                >
                  {TASK.many}
                </NavItem>
                <NavItem to="/portfolios">{PROJECT.many}</NavItem>
                {/* 026 live-check gap: the AuthApi always had signOut; nothing
                    rendered it — Cognito users had no way out of a session. */}
                {auth.user !== null && <AccountMenu signOut={() => auth.signOut()} />}
              </div>
            </NavBar>
            {base !== null && (
              <NavBar aria-label="Task" className="shrink-0 bg-ground">
                <div className="flex min-w-0 items-center gap-2">
                  {project.data !== undefined && (
                    <>
                      <span className="truncate text-lead font-semibold text-navy">
                        {scrub(project.data.name)}
                      </span>
                      <ProjectSettingsMenu
                        projectId={project.data.project_id}
                        projectName={project.data.name}
                      />
                    </>
                  )}
                </div>
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
              </NavBar>
            )}
            <SensitiveInfoBanner />
            {/* Cross-tab pause banner (028 strand 14 — pause salience): a
                paused run must be unmissable from every tab; the banner jumps
                straight to the waiting check-in. */}
            {hasPendingCheckIn && base !== null && (
              <div role="status" className="shrink-0 border-b border-orange bg-orange/10 px-5 py-2">
                <NavItem to={base}>
                  <span className="text-body font-semibold text-navy">
                    The analysis is paused — a check-in is waiting on you. Go to the check-in →
                  </span>
                </NavItem>
              </div>
            )}
            {/* Chat beside every project view outside the workspace (029
                rev 3.4): the workspace already hosts the full conversation
                rail, so the panel mounts everywhere else in the project. */}
            <div
              className={cn(
                "flex min-w-0 flex-1",
                base !== null && "min-h-0 overflow-hidden",
                chatOpen && "lg:min-h-0",
              )}
            >
              {/* Chat on the LEFT — parity with the workspace rail. Its own
                  boundary: a render error in the chat subtree must not take
                  out the rest of the shell (nav, the routed view). */}
              {showChatPanel && (
                <ErrorBoundary key={projectId}>
                  <ChatSidePanel projectId={projectId ?? ""} />
                </ErrorBoundary>
              )}
              <div
                className={cn(
                  "min-h-0 min-w-0 flex-1",
                  inWorkspace ? "overflow-hidden" : "overflow-y-auto",
                )}
              >
                <ErrorBoundary key={location.pathname}>
                  <Outlet />
                </ErrorBoundary>
              </div>
            </div>
            <AppFooter />
          </div>
        </TitleMarkerProvider>
      </TooltipProvider>
    </ToastProvider>
  );
}
