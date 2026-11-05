import { useState } from "react";

import { useAuth } from "../auth";
import { CloseButton } from "../ui/brand/CloseButton";

export const SENSITIVE_INFO_BANNER_KEY = "policy-atlas.dismiss-sensitive-banner";

function readDismissed(): boolean {
  try {
    return sessionStorage.getItem(SENSITIVE_INFO_BANNER_KEY) === "1";
  } catch {
    return false;
  }
}

function persistDismissed(): void {
  try {
    sessionStorage.setItem(SENSITIVE_INFO_BANNER_KEY, "1");
  } catch {
    // sessionStorage can throw in private mode; still hide for this mount.
  }
}

/** Narrow Nesta-red warning under the global nav on authenticated pages. */
export function SensitiveInfoBanner() {
  const auth = useAuth();
  const [dismissed, setDismissed] = useState(readDismissed);

  if (auth.user === null || dismissed) return null;

  return (
    <div
      role="status"
      className="flex shrink-0 items-center justify-between gap-3 bg-red px-5 py-1.5 text-body text-white"
    >
      <p>Do not enter sensitive or confidential information.</p>
      <CloseButton
        aria-label="Dismiss warning"
        tone="onRed"
        className="-my-1.5"
        onClick={() => {
          persistDismissed();
          setDismissed(true);
        }}
      />
    </div>
  );
}
