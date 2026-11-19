/**
 * Page events for product analytics (in-app feedback, the last step).
 *
 * `TrackEvent` sends one event when a page opens. `TrackAction` gives its
 * child a function to call for an action such as an export. Both do nothing
 * unless the `analytics` element is on, and neither adds anything to the page.
 */
import { useEffect, type ReactNode } from "react";

import { useTrackEvent, type AnalyticsEvent } from "../../api/feedback";
import { feedbackEnabled } from "../../lib/feedback";

/** Sends the event once for each task that the page opens on. */
function ActiveTrackEvent({ event, taskId }: { event: AnalyticsEvent; taskId?: string }) {
  const track = useTrackEvent();
  useEffect(() => {
    track(event, taskId);
  }, [track, event, taskId]);
  return null;
}

/**
 * Send one page event when the page opens.
 *
 * Args:
 *   event: The event name, from the API's closed list.
 *   taskId: The task that the page shows, if any.
 */
export function TrackEvent({ event, taskId }: { event: AnalyticsEvent; taskId?: string }) {
  if (!feedbackEnabled("analytics")) return null;
  return <ActiveTrackEvent event={event} taskId={taskId} />;
}

/**
 * Render a control that reports an action, for example an export.
 *
 * A component and not a hook, so that the API client is touched only when
 * the `analytics` element is on.
 *
 * Args:
 *   event: The event name.
 *   taskId: The task that the page shows, if any.
 *   children: Gets the function to call when the action happens. With
 *     analytics off the function does nothing.
 */
export function TrackAction({
  event,
  taskId,
  children,
}: {
  event: AnalyticsEvent;
  taskId?: string;
  children: (onAction: () => void) => ReactNode;
}) {
  if (!feedbackEnabled("analytics")) return <>{children(() => undefined)}</>;
  return (
    <ActiveTrackAction event={event} taskId={taskId}>
      {children}
    </ActiveTrackAction>
  );
}

/** The action reporter with analytics on. */
function ActiveTrackAction({
  event,
  taskId,
  children,
}: {
  event: AnalyticsEvent;
  taskId?: string;
  children: (onAction: () => void) => ReactNode;
}) {
  const track = useTrackEvent();
  return <>{children(() => track(event, taskId))}</>;
}
