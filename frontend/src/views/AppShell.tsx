import { useLayoutEffect, useState } from "react";
import { Outlet, useLocation, useParams } from "react-router";

import { useArchiveTask, useUpdateTask } from "../api/mutations";
import { useCheckIns, useMe, useTask, useTasks } from "../api/queries";
import { useAuth } from "../auth";
import { TitleMarkerProvider } from "../lib/title";
import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { StatusDot } from "../ui/brand/Card";
import { cn } from "../ui/brand/cn";
import { LifecycleBar } from "../ui/brand/LifecycleBar";
import { NavBar, NavHomeLink, NavItem } from "../ui/brand/Nav";
import { COPY, PROJECT, TASK, TENANCY_COPY } from "../lib/vocabulary";
import { lifecycleTabs, publicLifecycleTabs, withChat } from "./lifecycle";
import { PublicViewProvider } from "./publicView";
import { ErrorBoundary } from "../ui/feedback/ErrorBoundary";
import { RunStreamProvider } from "../store";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/radix/Popover";
import { AppFooter } from "./AppFooter";
import { SensitiveInfoBanner } from "./SensitiveInfoBanner";
import { ChatSidePanel } from "./workspace/chat/ChatSidePanel";
import { ToastProvider, useToast } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";

/** Task settings affordance (028 F.5): rename + archive, wired to the
 *  existing task mutations — the task-card pattern,
 *  condensed into the header popover. Rename saves inline; archive takes an
 *  explicit confirm step before the mutation fires. Visibility moved to the
 *  Share page (`ShareView`). */
function TaskSettingsMenu({
  taskId,
  taskName,
  isOwner,
}: {
  taskId: string;
  taskName: string;
  isOwner: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmingArchive, setConfirmingArchive] = useState(false);
  const [draftName, setDraftName] = useState(taskName);
  const update = useUpdateTask(taskId);
  const archive = useArchiveTask(taskId);
  const toast = useToast();

  // Non-owner (task 033 phase 10c, contract § 11 / rubric 37): every item
  // inside this popover is owner-gated — a non-owner has nothing to do here
  // at all, so the trigger itself must not render. Rev 1 of this gate
  // covered only the items, leaving a colleague a gear that opened onto an
  // empty popover.
  if (!isOwner) return null;

  const reset = () => {
    setEditing(false);
    setConfirmingArchive(false);
    setDraftName(taskName);
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
            description: "The task couldn't be renamed. Try again.",
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
          aria-label={COPY.taskSettings}
          title={COPY.taskSettings}
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
            <label className="sr-only" htmlFor="task-settings-name">
              {TASK.one} name
            </label>
            <input
              id="task-settings-name"
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
                The task couldn't be renamed. Try again.
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
            {/* Rename and archive are owner-only mutations (task 033 phase
                10c, contract § 11 / rubric 37) — hidden entirely for a
                non-owner. Rev 1 of this menu shipped these ungated: a
                colleague would see Rename, click, and get "The task
                couldn't be renamed." */}
            {isOwner && (
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="block w-full cursor-pointer text-left text-meta font-semibold text-navy hover:text-blue"
              >
                Rename
              </button>
            )}
            {isOwner && archive.isError && (
              <p role="alert" className="text-body text-red">
                The task couldn't be archived. Try again.
              </p>
            )}
            {isOwner &&
              (confirmingArchive ? (
                <div className="space-y-2 text-body text-grey">
                  <p>Archiving removes this task from your active tasks.</p>
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
                              description: "The task couldn't be archived. Try again.",
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
              ))}
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}

/**
 * Account menu: a user icon in the global bar, identity above Sign out
 * inside the popover (task 033 phase 10b, contract § 11 / rubric 41).
 *
 * Renders exactly what `/me` returns: `display_name` (ops already falls it
 * back to the `sub` rendering for an unenrolled caller — nothing here
 * duplicates that), `email` only when non-null, the organisation name or
 * `TENANCY_COPY.noOrganisation`, and `Administrator` only when `is_admin`.
 * The email line truncates with CSS (`truncate`) rather than being clipped
 * in script — a long address must not break the popover's fixed width.
 */
function AccountMenu({ signOut }: { signOut: () => void }) {
  const me = useMe();
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
      <PopoverContent align="end" className="w-56 p-1">
        {me.data !== undefined && (
          <div className="min-w-0 border-b border-line px-3 py-2">
            <p className="truncate text-meta font-bold text-navy">{scrub(me.data.display_name)}</p>
            {me.data.email != null && (
              <p className="truncate text-caption text-grey">{scrub(me.data.email)}</p>
            )}
            <p className="truncate text-caption text-grey">
              {me.data.organisation != null
                ? scrub(me.data.organisation.name)
                : TENANCY_COPY.noOrganisation}
            </p>
            {me.data.is_admin && (
              <p className="text-caption font-bold text-blue">{TENANCY_COPY.administrator}</p>
            )}
          </div>
        )}
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
  const { taskId } = useParams();
  const location = useLocation();
  const auth = useAuth();
  // Belt-and-braces while a run is active: the shell-owned run stream
  // already invalidates this query on `stage.completed` / `run.status`, but
  // polling covers a reconnect gap so lifecycle locking stays honest.
  const task = useTask(taskId ?? "", { pollWhileRunning: true });
  const base = taskId === undefined ? null : `/tasks/${taskId}`;
  // Public-leg access (task 037): a signed-in outsider reading a public Task
  // gets the same two-tab view as an anonymous visitor — no chat, no SSE,
  // no Plan/Share/History (their URLs redirect in LifecycleRoute).
  const publicAccess = task.data?.access === "public";
  // Review fix (task 037): `publicAccess` reads false while the task
  // query is still pending — same as a graded reader — so a cold visit to
  // a public Task briefly opened the run stream and mounted the chat panel
  // before access was known. Both gate on the query having resolved.
  const taskResolved = task.data !== undefined;
  // Outside a task, check all tasks so the nav logo animates even when the
  // user has navigated away. Cost: one list fetch when the shell mounts (once
  // per session — AppShell is the layout route), plus useTasks's own 15s
  // poll while any run is active; the query is shared with TasksListView.
  const allTasks = useTasks();
  const anyRunning =
    base !== null
      ? task.data?.latest_run?.status === "running"
      : (allTasks.data?.data.some((p) => p.latest_run?.status === "running") ?? false);
  const inWorkspace = base !== null && location.pathname === base;
  // Every task tab but Agent (038 V8, owner ruling 2026-09-05): the Agent
  // tab lists the same conversations in its own sidebar and shows the
  // selected one in its main column, so the overlay would be a second copy.
  const showChatPanel = base !== null && !inWorkspace && taskResolved && !publicAccess;
  // With a chat open beside the view, the two columns scroll independently —
  // the workspace's own two-pane behaviour (fixed viewport height, each
  // column owns its scroll). Closed, the page keeps its normal scroll.
  // `.get`, not `.has`: `?chat=` (present but empty) must read as closed,
  // matching `useActiveConversation`'s own non-empty check — otherwise a
  // bare `?chat=` opens a panel bound to conversation id "".
  const chatParam = new URLSearchParams(location.search).get("chat") || null;
  const chatOpen = showChatPanel && chatParam !== null;
  // Non-Plan task tabs: footer rides the shell scroll pane. Plan keeps its
  // own inner chat scroll, so the footer mounts there (PlanningPane) instead
  // of sticking under the composer.
  const footerInScrollPane = base !== null && !inWorkspace;

  // Pending check-in visibility outside the workspace (contract strand 14):
  // poll cheaply for a pending check-in only while the user isn't already on
  // the workspace view (where the check-in card itself is the live source of
  // truth) — the nav badge and title marker exist precisely to be seen from
  // everywhere else.
  //
  // Owner-scoped (task 033 phase 10b, contract § 11 / rubric 38): steering
  // is owner-only, so a colleague reading an org-shared Task must never be
  // told a check-in is "waiting on you" — this used to poll and show for
  // every viewer. `task.data?.is_owner` gates both the poll (cheapest
  // honest rule: don't even ask) and, transitively through `hasPendingCheckIn`
  // below, the nav badge, the lifecycle-tab marker and the cross-tab banner.
  const isOwner = task.data?.is_owner === true;
  const pendingCheckIns = useCheckIns(taskId ?? "", "pending", {
    enabled: base !== null && !inWorkspace && isOwner,
    refetchInterval: 15_000,
  });
  const hasPendingCheckIn =
    base !== null && !inWorkspace && isOwner && (pendingCheckIns.data?.data.length ?? 0) > 0;

  // Task views lock to the viewport so the app/lifecycle chrome stays put
  // and only the panes below scroll. List pages keep normal document scroll.
  useLayoutEffect(() => {
    if (base === null) return undefined;
    document.documentElement.classList.add("overflow-hidden");
    return () => document.documentElement.classList.remove("overflow-hidden");
  }, [base]);

  const shellChrome = (
    <div
      className={cn(
        "flex w-full min-w-0 max-w-full flex-col",
        base === null ? "min-h-svh" : "h-svh overflow-hidden",
      )}
    >
      <NavBar aria-label="App" className="shrink-0">
        <NavHomeLink running={anyRunning} />
        <div className="flex items-center gap-5">
          <NavItem to="/new" end>
            {COPY.navNew}
          </NavItem>
          <NavItem
            to="/"
            match={(path) => path === "/" || path.startsWith("/tasks/")}
          >
            {TASK.many}
          </NavItem>
          <NavItem to="/projects">{PROJECT.many}</NavItem>
          {/* 026 live-check gap: the AuthApi always had signOut; nothing
              rendered it — Cognito users had no way out of a session. */}
          {auth.user !== null && <AccountMenu signOut={() => auth.signOut()} />}
        </div>
      </NavBar>
      {base !== null && (
        <NavBar aria-label={TASK.one} className="shrink-0 bg-ground">
          <div className="flex min-w-0 items-center gap-2">
            {task.data !== undefined && (
              <>
                <span className="truncate text-lead font-semibold text-navy">
                  {scrub(task.data.name)}
                </span>
                <TaskSettingsMenu
                  taskId={task.data.task_id}
                  taskName={task.data.name}
                  isOwner={task.data.is_owner}
                />
              </>
            )}
          </div>
          <LifecycleBar
            hint={COPY.lockedHint}
            items={withChat(
              publicAccess
                ? publicLifecycleTabs(base)
                : lifecycleTabs(base, task.data?.latest_run?.status),
              chatParam,
            ).map((item) =>
              item.tab === "agent" && hasPendingCheckIn
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
      {/* The Agent overlay beside every task view outside the Agent tab
          (029 rev 3.4, 038 V8): the Agent tab hosts the conversation list
          and the conversation itself, so the panel mounts everywhere else. */}
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
          <ErrorBoundary key={taskId}>
            <ChatSidePanel taskId={taskId ?? ""} isOwner={isOwner} />
          </ErrorBoundary>
        )}
        <div
          data-testid={footerInScrollPane ? "task-scroll-pane" : undefined}
          className={cn(
            "min-h-0 min-w-0 flex-1",
            inWorkspace ? "overflow-hidden" : "overflow-y-auto [scrollbar-gutter:stable]",
            // The pane is a flex column only to pin the footer with
            // `mt-auto`; children must never flex-shrink, or a view
            // root with an explicit min-height (Sources' `min-h-full`)
            // gets squashed to one viewport and the footer lands
            // mid-content.
            footerInScrollPane && "flex flex-col [&>*]:shrink-0",
          )}
        >
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
          {footerInScrollPane && <AppFooter />}
        </div>
      </div>
      {/* List pages only — Plan hosts its own footer in the chat scroll. */}
      {base === null && <AppFooter />}
    </div>
  );

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <TitleMarkerProvider active={hasPendingCheckIn}>
          <PublicViewProvider value={publicAccess}>
            {taskId !== undefined ? (
              // `connect` stays false until the task query resolves, then
              // flips false permanently once a public-leg read identifies the
              // Task (the events route is not on the public surface) — for
              // entitled readers it flips true and stays there. Before that
              // resolution, access is unknown, so this must not connect
              // either (review fix, task 037).
              <RunStreamProvider taskId={taskId} connect={taskResolved && !publicAccess}>
                {shellChrome}
              </RunStreamProvider>
            ) : (
              shellChrome
            )}
          </PublicViewProvider>
        </TitleMarkerProvider>
      </TooltipProvider>
    </ToastProvider>
  );
}
