import { Card } from "../brand/Card";
import { useDocumentTitle } from "../../lib/title";

/** Owner-indistinguishable absence copy for missing or archived resources. */
export function NotFoundView() {
  useDocumentTitle("Not found");
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <Card className="p-6">
        <h1 className="font-display text-title text-navy">This task is unavailable</h1>
        <p className="mt-3 text-body text-grey">It may have been removed, archived, or you may not have access to it.</p>
      </Card>
    </main>
  );
}
