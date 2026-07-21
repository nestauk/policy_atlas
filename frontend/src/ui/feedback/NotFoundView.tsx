import { Card } from "../brand/Card";

/** Owner-indistinguishable absence copy for missing or archived resources. */
export function NotFoundView() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <Card className="p-6">
        <h1 className="font-display text-2xl text-navy">This project is unavailable</h1>
        <p className="mt-3 text-sm text-grey">It may have been removed, archived, or you may not have access to it.</p>
      </Card>
    </main>
  );
}
