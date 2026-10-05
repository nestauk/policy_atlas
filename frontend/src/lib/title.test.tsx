import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TitleMarkerProvider, useDocumentTitle } from "./title";

describe("useDocumentTitle", () => {
  it("joins non-empty parts and always appends Policy Atlas", () => {
    renderHook(() => useDocumentTitle("Acme task", "Workspace"));
    expect(document.title).toBe("Acme task · Workspace · Policy Atlas");
  });

  it("skips empty/absent parts (e.g. a task name still loading)", () => {
    renderHook(() => useDocumentTitle(undefined, "Workspace"));
    expect(document.title).toBe("Workspace · Policy Atlas");
  });

  it("renders the landing title with just the view name", () => {
    renderHook(() => useDocumentTitle("Projects"));
    expect(document.title).toBe("Projects · Policy Atlas");
  });

  it("prefixes the pending-check-in marker when the marker context is active", () => {
    renderHook(() => useDocumentTitle("Sources"), {
      wrapper: ({ children }) => <TitleMarkerProvider active>{children}</TitleMarkerProvider>,
    });
    expect(document.title).toBe("● Sources · Policy Atlas");
  });
});
