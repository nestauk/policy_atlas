import { useEffect, useState } from "react";
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

  // Land on the stashed deep link after a sign-in round trip (task 038 V11).
  // `OidcAuthProvider.onSigninCallback` restores it with
  // `window.history.replaceState`, which React Router does not observe, and
  // both routers are module-level singletons created (and initialised) at
  // import time — so the authenticated router mounts at the location its
  // history captured before the redirect, and the landing route renders on
  // the deep link's URL until a reload. Sync it once, and only on mismatch.
  //
  // Same-origin by construction: the destination is `window.location`, which
  // `replaceState` only ever set to a same-origin URL (it throws on any
  // other), and a `replace` navigation never falls back to
  // `location.assign`. The guard below keeps that invariant local should
  // either control change.
  useEffect(() => {
    if (status !== "authenticated") return;
    const target = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (!target.startsWith("/") || target.startsWith("//")) return;
    const at = authenticatedRouter.state.location;
    if (`${at.pathname}${at.search}${at.hash}` === target) return;
    void authenticatedRouter.navigate(target, { replace: true });
  }, [status]);

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

function App() {
  return (
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <AppRouter />
      </QueryClientProvider>
    </AuthProvider>
  );
}

export default App;
