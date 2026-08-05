import { Button } from "../brand/Button";
import { Card } from "../brand/Card";

/** Terminal timeline entry for a run interrupted before it could finish. */
export function InterruptedRunCard({ onStartFreshRun }: { onStartFreshRun: () => void | Promise<void> }) {
  return (
    <Card className="border-orange p-4">
      <h2 className="font-display text-heading text-navy">This run was interrupted</h2>
      <p className="mt-1 text-meta text-grey">Its partial results remain available. Start a new run when you are ready.</p>
      <Button className="mt-4" onClick={() => void onStartFreshRun()}>Start a fresh run</Button>
    </Card>
  );
}
