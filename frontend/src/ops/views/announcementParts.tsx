import { ToneSquare } from "../../ui/brand/EvidenceMarks";
import type { ToneColour } from "../../ui/brand/evidence";
import { NavLogo } from "../../ui/brand/Nav";
import { Figures } from "../../lib/figures";
import { formatCount } from "../../lib/format";
import type { AnnouncementKind, AnnouncementResult, RecipientPreview } from "../api";

/* The announcement pages' shared words and the email preview (design annex
   § Compose, § Result page, § The email). */

export const KIND_WORDS: Record<AnnouncementKind, string> = {
  product_update: "Product update",
  service_notice: "Service notice",
};

/** Why a person is left out, in the annex's words and order. */
export const LEFT_OUT_WORDS: Record<string, string> = {
  unsubscribed: "unsubscribed from product updates",
  not_signed_in: "has not signed in yet",
  deactivated: "deactivated",
  no_email: "no email address",
  suppressed_bounce: "the address bounced before",
  suppressed_complaint: "marked our email as spam",
};

/** A mail service's failure code in words. */
export function failureWords(code: string | null): string {
  if (code === "MessageRejected") return "the mail service refused the email";
  if (code !== null && ["TooManyRequestsException", "Throttling", "ThrottlingException", "LimitExceededException"].includes(code)) {
    return "the mail service was busy";
  }
  if (code === "AccountSendingPausedException" || code === "SendingPausedException") {
    return "sending is paused for this account";
  }
  return "the email could not be sent";
}

/** How many are left out, from the server's counts by reason. */
export function leftOutTotal(preview: RecipientPreview): number {
  return Object.values(preview.left_out).reduce((sum, n) => sum + n, 0);
}

/** "2 unsubscribed from product updates, 1 deactivated", in the annex's order. */
export function leftOutReasons(preview: RecipientPreview): string {
  return Object.keys(LEFT_OUT_WORDS)
    .filter((reason) => (preview.left_out[reason] ?? 0) > 0)
    .map((reason) => `${formatCount(preview.left_out[reason])} ${LEFT_OUT_WORDS[reason]}`)
    .join(", ");
}

/**
 * One person's result: its mark's colour and its words. `live` says a
 * `sending` row may still finish (the announcement or its retry is under two
 * minutes old); otherwise a stopped server left it, and it reads "Not confirmed".
 */
export function resultWords(row: Pick<AnnouncementResult, "status" | "reason" | "overlay">, live: boolean): { colour: ToneColour; words: string } {
  switch (row.status) {
    case "left_out":
      return { colour: "grey", words: `Left out: ${LEFT_OUT_WORDS[row.reason ?? ""] ?? row.reason ?? ""}` };
    case "pending":
      return { colour: "yellow", words: "Waiting" };
    case "sending":
      return live ? { colour: "yellow", words: "Sending" } : { colour: "grey", words: "Not confirmed" };
    case "failed":
      return { colour: "red", words: `Failed: ${failureWords(row.reason)}` };
    default:
      if (row.overlay === "bounced") return { colour: "red", words: "Bounced: the address does not exist" };
      if (row.overlay === "marked_as_spam") return { colour: "red", words: "Marked as spam" };
      return { colour: "green", words: "Sent" };
  }
}

/**
 * Where a row stands in the result table: the rows that need attention first
 * (Failed, Not confirmed, Bounced and Marked as spam), then Left out, then
 * Waiting and Sending, then Sent.
 */
export function resultRank(row: Pick<AnnouncementResult, "status" | "overlay">, live: boolean): number {
  switch (row.status) {
    case "failed":
      return 0;
    case "sending":
      return live ? 4 : 1;
    case "left_out":
      return 3;
    case "pending":
      return 4;
    default:
      return row.overlay === null ? 5 : 2;
  }
}

/** A status as a mark and a word, never a colour alone. */
export function Marked({ colour, children }: { colour: ToneColour; children: string }) {
  return (
    <span className="inline-flex items-baseline gap-2">
      <ToneSquare colour={colour} className="self-center" />
      <span>
        <Figures text={children} />
      </span>
    </span>
  );
}

/** The body as the server reads it: blocks split on an empty line, runs of "- " lines as a list. */
function blocks(body: string): Array<{ list: boolean; lines: string[] }> {
  const runs: Array<{ list: boolean; lines: string[] }> = [];
  const text = body.replace(/\r\n/g, "\n").trim();
  if (text === "") return runs;
  for (const block of text.split(/\n\s*\n/)) {
    let previous: boolean | null = null;
    for (const line of block.split("\n")) {
      const item = line.startsWith("- ");
      const content = item ? line.slice(2) : line;
      if (item === previous) runs[runs.length - 1].lines.push(content);
      else runs.push({ list: item, lines: [content] });
      previous = item;
    }
  }
  return runs;
}

/**
 * The email as the person gets it, drawn by the page from the fields. The
 * picture is the browser's own copy (`src`) when there is one; otherwise a
 * box with its description, because the ops pages may not load pictures
 * from the public site.
 */
export function EmailPreview({
  kind,
  subject,
  body,
  buttonLabel,
  picture,
}: {
  kind: AnnouncementKind;
  subject: string;
  body: string;
  buttonLabel: string | null;
  picture: { src: string | null; alt: string } | null;
}) {
  return (
    <div className="border border-line bg-ground p-4 max-md:p-2">
      <div className="flex flex-col gap-3 bg-paper p-6 text-body text-ink max-md:p-4">
        <div>
          <NavLogo />
        </div>
        <p className="mt-2 text-heading font-bold text-navy [overflow-wrap:anywhere]">{subject}</p>
        {blocks(body).map((run, index) =>
          run.list ? (
            <ul key={index} className="list-disc pl-5">
              {run.lines.map((line, at) => (
                <li key={at}>{line}</li>
              ))}
            </ul>
          ) : (
            <p key={index} className="[overflow-wrap:anywhere]">
              {run.lines.map((line, at) => (
                <span key={at}>
                  {at > 0 && <br />}
                  {line}
                </span>
              ))}
            </p>
          ),
        )}
        {picture !== null &&
          (picture.src !== null ? (
            <img src={picture.src} alt={picture.alt} className="block h-auto max-w-full" />
          ) : (
            <div role="img" aria-label={picture.alt} className="border border-line bg-blue-tint-2 px-4 py-8 text-meta text-grey">
              {picture.alt}
            </div>
          ))}
        {buttonLabel !== null && buttonLabel !== "" && (
          <span className="mt-2 self-start bg-navy px-5 py-3 text-meta font-bold text-white">{buttonLabel}</span>
        )}
        <div className="mt-3 border-t border-line pt-4 text-meta text-grey">
          {kind === "product_update" ? (
            <p>
              You get this email because you have a Policy Atlas account. <span className="underline">Unsubscribe from product updates</span>. We still send service notices about your account.
            </p>
          ) : (
            <p>You get this email because you have a Policy Atlas account. This is a service notice about your account.</p>
          )}
          <p className="mt-2">Questions? Reply to this email or write to discoveryhub@nesta.org.uk.</p>
        </div>
      </div>
    </div>
  );
}
