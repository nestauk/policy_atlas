import { createElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthContext } from "../auth/AuthContext";
import type { AuthApi } from "../auth/types";
import { taskNameFromQuestion, useCreateTask, useUpdatePortfolio, useUpdateProject } from "./mutations";

describe("taskNameFromQuestion", () => {
  it("drops a trailing question mark", () => {
    expect(taskNameFromQuestion("What works?")).toBe("What works");
  });

  it("collapses whitespace", () => {
    expect(taskNameFromQuestion("What   works   best?")).toBe("What works best");
  });

  it("returns short questions unchanged", () => {
    expect(taskNameFromQuestion("Short question")).toBe("Short question");
  });

  it("clips long questions on a word boundary with an ellipsis, never exceeding the max by more than the ellipsis", () => {
    const long = "word ".repeat(30).trim();
    const max = 80;
    const result = taskNameFromQuestion(long, max);
    expect(result.endsWith("…")).toBe(true);
    expect(result.length).toBeLessThanOrEqual(max + 1);
    expect(result.slice(0, -1)).not.toMatch(/\s$/);
  });
});

// Task 033 phase 10a: cross-family cache invalidation — a portfolio-family
// mutation must reach the project family (and vice versa), or a scoped list
// keeps showing pre-mutation rows until an unrelated refetch. Invalidation
// is asserted by prefix (`["portfolios"]`/`["projects"]`, not the full
// filtered key), which is what makes it cover every `scope` variant
// currently cached.
function makeAuth(): AuthApi {
  return {
    getAccessToken: async () => "token-a",
    signIn: () => undefined,
    signOut: () => undefined,
    onUnauthenticated: () => undefined,
    user: { sub: "user-1" },
    status: "authenticated",
  };
}

function wrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      AuthContext.Provider,
      { value: makeAuth() },
      createElement(QueryClientProvider, { client: queryClient }, children),
    );
  };
}

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:3000");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("cross-family cache invalidation (task 033 phase 10a)", () => {
  it("useUpdatePortfolio invalidates both the portfolio and project families", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            portfolio_id: "p1",
            name: "Housing",
            description: null,
            created_at: "2026-01-01T00:00:00Z",
            task_count: 2,
            visibility: "private",
            is_owner: true,
            owner_display: "Ada Lovelace",
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdatePortfolio("p1"), { wrapper: wrapper(queryClient) });
    result.current.mutate({ visibility: "private" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(["portfolios"]);
    expect(invalidatedKeys).toContainEqual(["projects"]);
  });

  it("useUpdateProject invalidates both the project and portfolio families", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            project_id: "proj-1",
            name: "Task",
            status: "active",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            latest_run: null,
            portfolio_id: "p1",
            visibility: "org",
            is_owner: true,
            owner_display: "Ada Lovelace",
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useUpdateProject("proj-1"), { wrapper: wrapper(queryClient) });
    result.current.mutate({ portfolio_id: "p1" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(["projects"]);
    expect(invalidatedKeys).toContainEqual(["portfolios"]);
  });

  it("useCreateTask invalidates both families when it assigns a portfolio (its PATCH changes that portfolio's task_count)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const request = input as Request;
        if (request.method === "POST" && request.url.endsWith("/api/v1/projects")) {
          return new Response(
            JSON.stringify({
              project_id: "proj-1",
              name: "A question",
              status: "active",
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
              latest_run: null,
              portfolio_id: null,
              visibility: "org",
              is_owner: true,
              owner_display: "Ada Lovelace",
            }),
            { headers: { "Content-Type": "application/json" } },
          );
        }
        if (request.method === "PATCH" && request.url.endsWith("/api/v1/projects/proj-1")) {
          return new Response(JSON.stringify({ project_id: "proj-1" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (request.method === "POST" && request.url.endsWith("/planning-turns")) {
          return new Response(JSON.stringify({ turn_index: 1 }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        throw new Error(`unexpected fetch: ${request.method} ${request.url}`);
      }),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useCreateTask(), { wrapper: wrapper(queryClient) });
    result.current.mutate({ question: "A question", portfolioId: "portfolio-1" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(["projects"]);
    expect(invalidatedKeys).toContainEqual(["portfolios"]);
  });
});

// The portfolio-assignment PATCH inside `useCreateTask` used to fire and
// forget: openapi-fetch never throws on a 4xx of its own, so an unchecked
// result left a colleague picking a colleague-owned (readable but not
// writable) project with a task created and silently left unassigned.
describe("useCreateTask — the portfolio-assignment PATCH result is checked", () => {
  function projectResponse() {
    return new Response(
      JSON.stringify({
        project_id: "proj-1",
        name: "A question",
        status: "active",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        latest_run: null,
        portfolio_id: null,
        visibility: "org",
        is_owner: true,
        owner_display: "Ada Lovelace",
      }),
      { headers: { "Content-Type": "application/json" } },
    );
  }

  it("surfaces the PATCH's error instead of silently leaving the task unassigned", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.endsWith("/api/v1/projects")) {
        return projectResponse();
      }
      if (request.method === "PATCH" && request.url.endsWith("/api/v1/projects/proj-1")) {
        return new Response(
          JSON.stringify({ error: { code: "forbidden", message: "Not the owner." } }),
          { status: 403, headers: { "Content-Type": "application/json" } },
        );
      }
      throw new Error(`unexpected fetch: ${request.method} ${request.url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useCreateTask(), { wrapper: wrapper(queryClient) });
    result.current.mutate({ question: "A question", portfolioId: "portfolio-1" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect((result.current.error as { code?: string } | null)?.code).toBe("forbidden");

    // The opening planning turn never fires once the assignment is refused.
    const calledUrls = fetchMock.mock.calls.map(([req]) => (req as Request).url);
    expect(calledUrls.some((url) => url.includes("/planning-turns"))).toBe(false);
  });

  it("still succeeds when the caller owns the chosen project", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const request = input as Request;
      if (request.method === "POST" && request.url.endsWith("/api/v1/projects")) {
        return projectResponse();
      }
      if (request.method === "PATCH" && request.url.endsWith("/api/v1/projects/proj-1")) {
        return new Response(JSON.stringify({ project_id: "proj-1" }), {
          headers: { "Content-Type": "application/json" },
        });
      }
      if (request.method === "POST" && request.url.endsWith("/planning-turns")) {
        return new Response(JSON.stringify({ turn_index: 1 }), {
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`unexpected fetch: ${request.method} ${request.url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useCreateTask(), { wrapper: wrapper(queryClient) });
    result.current.mutate({ question: "A question", portfolioId: "portfolio-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
