import { useEffect, useRef } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";

import { AuthProvider, useAuth } from "./auth";
import { authenticatedRouter, publicRouter } from "./routes";

const queryClient = new QueryClient();

/**
 * Pick the public splash router or the authenticated app router from auth
 * status. Remounts on status change so `/` cannot resolve ambiguously.
 *
 * The query cache is cleared on every settled identity change (task 037):
 * the client outlives the router swap and its keys carry only ids, so
 * without the flush a just-signed-out owner could briefly see cached
 * private data on a public Task's URL before the tokenless refetch lands.
 */
function AppRouter() {
  const auth = useAuth();
  const status = auth.status;
  const lastSettled = useRef<string | null>(null);

  useEffect(() => {
    if (status === "loading") return;
    if (lastSettled.current !== null && lastSettled.current !== status) {
      queryClient.clear();
    }
    lastSettled.current = status;
  }, [status]);

  if (status === "loading") {
    return (
      <p role="status" className="text-meta text-grey">
        Loading…
      </p>
    );
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
