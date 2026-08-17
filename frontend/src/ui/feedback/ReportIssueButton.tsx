import { useState } from "react";
import { useLocation } from "react-router";

import { useReportIssue } from "../../api/mutations";
import { Button } from "../brand/Button";
import { Sheet, SheetContent } from "../radix/Sheet";
import { useToast } from "../radix/Toast";

/** "Report an issue": a free-text channel with no LLM anywhere in it.
 *
 *  Deliberately separate from the chat launcher — chat answers you, this only
 *  records what you noticed. The text is stored verbatim against the project
 *  and the page it was raised from.
 *
 *  Lives in the nav rather than as a second floating button: the bottom-right
 *  corner is the toast viewport (`fixed bottom-4 right-4 z-50 w-96`), so a
 *  button there is covered by the very error toast a user wants to report. */
export function ReportIssueButton({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const location = useLocation();
  const report = useReportIssue(projectId);
  const toast = useToast();
  const trimmed = value.trim();

  // Every close path (Cancel, Esc, overlay, the ✕) routes through here, so a
  // stale failure notice can't greet the next open.
  const setSheetOpen = (next: boolean) => {
    setOpen(next);
    if (!next) setNotice(null);
  };

  const submit = () => {
    setNotice(null);
    report.mutate(
      { body: trimmed, pagePath: location.pathname },
      {
        onSuccess: () => {
          setValue("");
          setSheetOpen(false);
          toast.toast({
            title: "Thank you — that's been logged",
            description: "We read every report. There's no reply here.",
            tone: "default",
          });
        },
        // Inline copy is load-bearing (the sheet stays open with the text
        // intact so nothing is retyped); the toast makes the failure visible
        // if the sheet has been scrolled or dismissed.
        onError: () => {
          setNotice("That couldn't be sent. Your text is still here — try again in a moment.");
          toast.toast({
            title: "The report couldn't be sent",
            description: "Nothing was logged.",
            tone: "error",
          });
        },
      },
    );
  };

  return (
    <>
      <button
        type="button"
        title="Report an issue"
        onClick={() => setSheetOpen(true)}
        className="inline-flex cursor-pointer items-center gap-1.5 text-meta text-grey hover:text-navy focus-visible:outline-2 focus-visible:outline-blue"
      >
        <svg
          aria-hidden="true"
          width="16"
          height="16"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        >
          <circle cx="10" cy="10" r="7.25" />
          <path d="M10 6.25v5" />
          <path d="M10 13.75v.01" />
        </svg>
        Report an issue
      </button>
      <Sheet open={open} onOpenChange={setSheetOpen}>
        {open && (
          <SheetContent
            title="Report an issue"
            description="Tell us what you noticed. This goes straight to the team — nothing here is answered by a model."
          >
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (trimmed.length > 0 && !report.isPending) submit();
              }}
              className="space-y-4"
            >
              <div>
                <label htmlFor="report-issue-body" className="sr-only">
                  What did you notice?
                </label>
                <textarea
                  id="report-issue-body"
                  autoFocus
                  rows={8}
                  maxLength={4000}
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                  placeholder="What happened, and what you expected instead."
                  className="w-full border border-line-2 bg-paper px-3 py-2 text-meta text-navy focus-visible:outline-2 focus-visible:outline-blue"
                />
              </div>
              {notice !== null && (
                <p role="alert" className="text-caption text-navy">
                  {notice}
                </p>
              )}
              <div className="flex items-center gap-2">
                <Button type="submit" size="sm" disabled={report.isPending || trimmed.length === 0}>
                  {report.isPending ? "Sending…" : "Send report"}
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setSheetOpen(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </SheetContent>
        )}
      </Sheet>
    </>
  );
}
