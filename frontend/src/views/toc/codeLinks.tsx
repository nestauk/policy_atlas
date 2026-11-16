import { Fragment, type ReactNode } from "react";
import { Link } from "react-router";

import { scrub } from "../../lib/scrub";
import { LINK_CLASS } from "../../ui/brand/inlineActions";

/**
 * Chat text with each box and connection code (S3, #5) as a link that opens
 * the Result tab with that box or connection selected, as a code in the
 * report does (round 6). "Result tab" links there too. Only codes the theory
 * has are linked, so ordinary words are never caught.
 */
export function TocCodeText({ text, taskId, codes }: { text: string; taskId: string; codes: ReadonlySet<string> }): ReactNode {
  const clean = scrub(text);
  const escaped = [...codes].sort((a, b) => b.length - a.length).map((code) => code.replace(/[#.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(?<![\\w#])(${[...escaped, "Result tab"].join("|")})(?!\\w)`, "g");
  const parts = clean.split(pattern);
  return parts.map((part, index) =>
    index % 2 === 0 ? (
      <Fragment key={index}>{part}</Fragment>
    ) : (
      <Link
        key={index}
        to={part === "Result tab" ? `/tasks/${taskId}/result` : `/tasks/${taskId}/result?focus=${encodeURIComponent(part)}`}
        className={LINK_CLASS}
      >
        {part}
      </Link>
    ),
  );
}
