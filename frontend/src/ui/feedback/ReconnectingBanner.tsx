import { useEffect, useState } from "react";

/** Live-stream disconnect signal, with a stale-data warning after 30 seconds. */
export function ReconnectingBanner({ connectionStatus }: { connectionStatus: "connected" | "reconnecting" }) {
  if (connectionStatus === "connected") return null;
  return <ReconnectingContent />;
}

function ReconnectingContent() {
  const [stale, setStale] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setStale(true), 30_000);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div role="status" className="border-b border-yellow bg-yellow-tint px-4 py-2 text-xs text-navy">
      Reconnecting to live updates…{stale ? " Updates may be stale." : ""}
    </div>
  );
}
