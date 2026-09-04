import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";

import { AuthProvider, useAuth } from "./auth";
import { authenticatedRouter, publicRouter } from "./routes";

export const queryClient = new QueryClient();

/**
 * Pick the public splash router or the authenticated app router from auth
 * status. Remounts on status change so `/` cannot resolve ambiguously.
 *
 * The query cache is cleared on every settled identity change (task 037),
 * inline during render rather than in an effect: an effect fires AFTER the
 * router below has already swapped and rendered, so a just-signed-out owner
 * could still see a frame of cached private data on a public Task's URL
 * before the flush caught up. The client outlives the router swap and its
 * keys carry only ids, so the clear has to land before the router is chosen.
 */
function AppRouter() {
  const auth = useAuth();
  const status = auth.status;
  const [lastSettled, setLastSettled] = useState<string | null>(null);

  if (status === "loading") {
    return (
      <p role="status" className="text-meta text-grey">
        Loading…
      </p>
    );
  }

  // Adjust state during render (React's documented pattern for reacting to
  // a prop/context change before children render) rather than in an effect,
  // so the clear is guaranteed to have happened before the router below
  // renders anything under the new identity. `clear()` is idempotent, so
  // StrictMode's double render is harmless.
  if (lastSettled !== status) {
    if (lastSettled !== null) {
      queryClient.clear();
    }
    setLastSettled(status);
  }

  const router = status === "authenticated" ? authenticatedRouter : publicRouter;
  return <RouterProvider key={status} router={router} />;
}

export function App() {
  return (
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <AppRouter />
      </QueryClientProvider>
    </AuthProvider>
  );
}

export default App;
