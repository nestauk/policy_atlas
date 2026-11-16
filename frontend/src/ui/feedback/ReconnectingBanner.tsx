import { useEffect, useState } from "react";

import { cn } from "../brand/cn";
import type { RunStreamState } from "../../store/types";

/** Live-stream disconnect signal, with a stale-data warning after 30
 *  seconds. Only a lapsed connection (`"reconnecting"`) shows the banner —
 *  the initial `"connecting"` state (before the first connection ever
 *  succeeds) is not a reconnect and stays silent. */
export function ReconnectingBanner({
  connectionStatus,
  className,
}: {
  connectionStatus: RunStreamState["connectionStatus"];
  className?: string;
}) {
  if (connectionStatus !== "reconnecting") return null;
  return <ReconnectingContent className={className} />;
}

/**
 * The reconnecting line (task 058, owner round 11): it takes the run status
 * bar's frame, so it starts after the rail and never runs under it: one line
 * at Meta size with the bar's 10 px vertical padding, its words where the
 * bar's words start (after the mark's column), on the Yellow Tint with a
 * Yellow hairline under it. Exported for the bar itself,
 * which shows it in place of its words while the stream reconnects.
 */
export function ReconnectingContent({ className }: { className?: string }) {
  const [stale, setStale] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setStale(true), 30_000);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div
      role="status"
      className={cn(
        "border-b border-yellow bg-yellow-tint py-2.5 pr-6 pl-[46px] text-meta leading-[1.55rem] text-navy max-md:pr-4 max-md:pl-[38px]",
        className,
      )}
    >
      Reconnecting to live updates…{stale ? " Updates may be stale." : ""}
    </div>
  );
}
