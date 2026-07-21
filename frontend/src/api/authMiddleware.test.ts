import { describe, expect, it, vi } from "vitest";

import type { AuthApi } from "../auth/types";
import { createAuthMiddleware } from "./authMiddleware";

function makeAuth(overrides: Partial<AuthApi> = {}): AuthApi {
  return {
    getAccessToken: vi.fn(async () => "token-a"),
    signIn: vi.fn(),
    signOut: vi.fn(),
    user: { sub: "user-1" },
    status: "authenticated",
    ...overrides,
    onUnauthenticated: overrides.onUnauthenticated ?? vi.fn(),
  };
}

/** Minimal stand-in for `openapi-fetch`'s `MiddlewareCallbackParams["options"]`. */
function mergedOptions() {
  return {
    baseUrl: "https://api.example",
    parseAs: "json" as const,
    querySerializer: () => "",
    bodySerializer: (body: unknown) => body,
    pathSerializer: (pathname: string) => pathname,
    fetch: globalThis.fetch,
  };
}

function callbackParams(request: Request) {
  return { request, schemaPath: "/x", params: {}, id: "test-request", options: mergedOptions() };
}

describe("createAuthMiddleware", () => {
  it("onRequest injects the bearer header from the active AuthApi", async () => {
    const middleware = createAuthMiddleware(makeAuth());
    const request = new Request("https://api.example/x");

    const result = await middleware.onRequest?.(callbackParams(request));

    expect((result as Request).headers.get("Authorization")).toBe("Bearer token-a");
  });

  it("onResponse retries once on 401 with a force-refreshed token, returning the retry", async () => {
    const getAccessToken = vi.fn(async (force?: boolean) => (force ? "token-b" : "token-a"));
    const middleware = createAuthMiddleware(makeAuth({ getAccessToken }));

    const request = new Request("https://api.example/x", {
      headers: { Authorization: "Bearer token-a" },
    });
    const originalResponse = new Response(null, { status: 401 });
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));

    const result = await middleware.onResponse?.({
      ...callbackParams(request),
      response: originalResponse,
    });

    expect(getAccessToken).toHaveBeenCalledWith(true);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const retriedRequest = fetchSpy.mock.calls[0][0] as Request;
    expect(retriedRequest.headers.get("Authorization")).toBe("Bearer token-b");
    expect((result as Response).status).toBe(200);

    fetchSpy.mockRestore();
  });

  it("surfaces the original 401 when the refresh yields no token", async () => {
    const getAccessToken = vi.fn(async (force?: boolean) => (force ? null : "token-a"));
    const middleware = createAuthMiddleware(makeAuth({ getAccessToken }));
    const request = new Request("https://api.example/x");
    const originalResponse = new Response(null, { status: 401 });

    const result = await middleware.onResponse?.({
      ...callbackParams(request),
      response: originalResponse,
    });

    expect(result).toBe(originalResponse);
  });

  it("retries a POST with its JSON body intact after a 401, even though the sent request's body was already consumed", async () => {
    const getAccessToken = vi.fn(async (force?: boolean) => (force ? "token-b" : "token-a"));
    const middleware = createAuthMiddleware(makeAuth({ getAccessToken }));

    const originalRequest = new Request("https://api.example/x", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hello: "world" }),
    });

    const afterOnRequest = await middleware.onRequest?.(callbackParams(originalRequest));
    const sentRequest = (afterOnRequest as Request | undefined) ?? originalRequest;

    // Simulate the real `fetch(sentRequest, ...)` call openapi-fetch makes
    // before `onResponse` ever runs — it consumes the body stream. A naive
    // `request.clone()` inside `onResponse` throws TypeError once that's
    // happened; this is the exact bug the pristine-clone stash fixes.
    await sentRequest.text();

    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));

    const originalResponse = new Response(null, { status: 401 });
    const result = await middleware.onResponse?.({
      ...callbackParams(sentRequest),
      response: originalResponse,
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const retriedRequest = fetchSpy.mock.calls[0][0] as Request;
    expect(retriedRequest.headers.get("Authorization")).toBe("Bearer token-b");
    await expect(retriedRequest.text()).resolves.toBe(JSON.stringify({ hello: "world" }));
    expect((result as Response).status).toBe(200);

    fetchSpy.mockRestore();
  });

  it("passes non-401 responses through untouched", async () => {
    const middleware = createAuthMiddleware(makeAuth());
    const request = new Request("https://api.example/x");
    const okResponse = new Response(null, { status: 200 });

    const result = await middleware.onResponse?.({ ...callbackParams(request), response: okResponse });

    expect(result).toBe(okResponse);
  });
});
