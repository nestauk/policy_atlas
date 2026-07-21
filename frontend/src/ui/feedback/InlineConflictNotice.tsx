import { useState } from "react";

import { conflictSentences, type ConflictCode } from "../../lib/errors";
import { Button } from "../brand/Button";

/** Trigger-local 409 recovery with an explicit refetch action. */
export function InlineConflictNotice({
  code,
  onRefetch,
}: {
  code: ConflictCode;
  onRefetch: () => void | Promise<void>;
}) {
  const [visible, setVisible] = useState(true);
  if (!visible) return null;

  return (
    <div role="alert" className="flex items-center gap-3 border border-orange bg-paper p-3 text-sm text-navy">
      <p className="flex-1">{conflictSentences[code]}</p>
      <Button variant="secondary" size="sm" onClick={() => void onRefetch()}>Refresh</Button>
      <Button variant="ghost" size="sm" onClick={() => setVisible(false)}>Dismiss</Button>
    </div>
  );
}
