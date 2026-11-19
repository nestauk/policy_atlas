import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";

import { AuthProvider, useAuth } from "../auth";
import { PAGE_COLUMN_CLASS } from "../ui/brand/PageHeader";
import { ToastProvider } from "../ui/radix/Toast";
import { opsRoutes } from "./routes";
import { Loading } from "./ui";

/** No automatic retries: a 403 or 409 will not change, and every failed
 *  read has its own "Try again". */
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, retryOnMount: false } } });

/** The router reads the address when it is made, so it is made once the
 *  sign-in has settled and a callback has put the deep link back. */
function RouterHost() {
  const [router] = useState(() => createBrowserRouter(opsRoutes));
  return <RouterProvider router={router} />;
}

function OpsRouter() {
  const auth = useAuth();
  if (auth.status === "loading") {
    return (
      <main className={PAGE_COLUMN_CLASS}>
        <Loading />
      </main>
    );
  }
  return <RouterHost />;
}

/** The ops pages: the shared sign-in, one query cache, the toasts and the router. */
export function OpsApp() {
  return (
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <OpsRouter />
        </ToastProvider>
      </QueryClientProvider>
    </AuthProvider>
  );
}
