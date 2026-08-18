import type { ReactNode } from "react";

import { useDocumentTitle } from "../../lib/title";

/**
 * Shared chrome for the public legal pages: a single prose column under
 * the app header, sized to the same measure as the rest of the product.
 */
export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated?: string;
  children: ReactNode;
}) {
  useDocumentTitle(title);
  return (
    <main className="mx-auto w-full max-w-prose-measure px-6 py-10">
      <h1 className="font-sans text-title font-extrabold text-navy">{title}</h1>
      {updated !== undefined && <p className="mt-2 text-meta text-grey">Last updated: {updated}</p>}
      <div className="mt-8 space-y-8">{children}</div>
    </main>
  );
}

/** Numbered section on a legal page. */
export function LegalSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="font-sans text-heading font-semibold text-navy">{title}</h2>
      <div className="space-y-3 text-body text-ink">{children}</div>
    </section>
  );
}

/** Bullet list used by the privacy notice's exclusion and rights sections. */
export function LegalList({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-2 pl-5">{children}</ul>;
}

/** Off-site privacy notices (AWS Cognito, Aurora, Bedrock). */
export function ExternalNoticeLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-navy underline hover:text-blue">
      {children}
    </a>
  );
}
