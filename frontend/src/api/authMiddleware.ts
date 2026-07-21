import type { Middleware } from "openapi-fetch";

import type { AuthApi } from "../auth/types";

/**
 * `openapi-fetch` middleware injecting `Authorization: Bearer <token>` from
 * the active `AuthApi`, with one silent-refresh-then-retry on a 401 —
 * still 401 after that surfaces as an ordinary unauthenticated response
 * (the caller sees the API's real 401 body, not a synthetic one).
 *
 * The retry replays a *pre-fetch* clone of the request, stashed during
 * `onRequest` before the underlying `fetch()` call ever touches its body.
 * Cloning a `Request` whose body stream has already been read (which is
 * exactly the state `request` is in by the time `onResponse` runs) throws
 * `TypeError` — the pristine stash is what makes retrying a POST with a
 * JSON body actually work.
 */
export function createAuthMiddleware(auth: AuthApi): Middleware {
  const pristineRequests = new WeakMap<Request, Request>();

  return {
    async onRequest({ request }) {
      // Clone before anything reads the body — this is the only point in
      // the lifecycle where the body stream is still untouched.
      pristineRequests.set(request, request.clone());

      const token = await auth.getAccessToken();
      if (token) {
        request.headers.set("Authorization", `Bearer ${token}`);
      }
      return request;
    },
    async onResponse({ request, response }) {
      if (response.status !== 401) {
        pristineRequests.delete(request); // no retry coming — release the clone
        return response;
      }

      const refreshed = await auth.getAccessToken(true);
      if (!refreshed) {
        pristineRequests.delete(request);
        return response; // no token to retry with — surface the 401 as-is
      }

      let retryRequest: Request;
      const pristine = pristineRequests.get(request);
      if (pristine !== undefined) {
        retryRequest = pristine;
      } else {
        try {
          retryRequest = request.clone();
        } catch {
          pristineRequests.delete(request);
          return response; // body already consumed and no stash — surface the 401
        }
      }
      pristineRequests.delete(request);

      retryRequest.headers.set("Authorization", `Bearer ${refreshed}`);
      return fetch(retryRequest);
    },
  };
}
