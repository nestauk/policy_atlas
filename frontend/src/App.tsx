import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";

import { AuthProvider, useAuth } from "./auth";
import { authenticatedRouter, publicRouter } from "./routes";

const queryClient = new QueryClient();

/**
 * Pick the public splash router or the authenticated app router from auth
 * status. Remounts on status change so `/` cannot resolve ambiguously.
 */
function AppRouter() {
  const auth = useAuth();

  if (auth.status === "loading") {
    return (
      <p role="status" className="text-meta text-grey">
        Loading…
      </p>
    );
  }

  const router = auth.status === "authenticated" ? authenticatedRouter : publicRouter;
  return <RouterProvider key={auth.status} router={router} />;
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
