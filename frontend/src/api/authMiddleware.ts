import type { Middleware } from "openapi-fetch";

import type { AuthApi } from "../auth/types";

/**
 * `openapi-fetch` middleware injecting `Authorization: Bearer <token>` from
 * the active `AuthApi`, with one silent-refresh-then-retry on a 401 —
 * still 401 after that surfaces as an ordinary unauthenticated response
 * (the caller sees the API's real 401 body, not a synthetic one).
 */
export function createAuthMiddleware(auth: AuthApi): Middleware {
  return {
    async onRequest({ request }) {
      const token = await auth.getAccessToken();
      if (token) {
        request.headers.set("Authorization", `Bearer ${token}`);
      }
      return request;
    },
    async onResponse({ request, response }) {
      if (response.status !== 401) return response;

      const refreshed = await auth.getAccessToken(true);
      if (!refreshed) return response; // no token to retry with — surface the 401 as-is

      const retryRequest = request.clone();
      retryRequest.headers.set("Authorization", `Bearer ${refreshed}`);
      return fetch(retryRequest);
    },
  };
}
