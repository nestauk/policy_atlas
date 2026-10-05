import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Without vitest globals, testing-library's auto-cleanup never registers —
// wire it explicitly so tests don't leak DOM into each other.
afterEach(() => {
  cleanup();
  // Web storage differs by runtime: inert under the local Node's experimental
  // `localStorage`, working in CI's jsdom — where a per-browser choice (the
  // chats sidebar open or shut) written by one test leaked into the next and
  // turned "Show chats" into "Hide chats" (038 review follow-on). Start every
  // test with empty storage wherever storage exists.
  for (const name of ["localStorage", "sessionStorage"] as const) {
    try {
      window[name]?.clear();
    } catch {
      // Storage unavailable here (the accessor itself may throw): nothing to clear.
    }
  }
});

// jsdom lacks the pointer-capture API Radix's swipe/press handling touches.
if (window.HTMLElement.prototype.hasPointerCapture === undefined) {
  window.HTMLElement.prototype.hasPointerCapture = () => false;
  window.HTMLElement.prototype.setPointerCapture = () => undefined;
  window.HTMLElement.prototype.releasePointerCapture = () => undefined;
}
// jsdom lacks scrollIntoView, which Radix focus management calls.
if (window.HTMLElement.prototype.scrollIntoView === undefined) {
  window.HTMLElement.prototype.scrollIntoView = () => undefined;
}
// jsdom lacks ResizeObserver, which the chat's bottom-pinning uses.
if (window.ResizeObserver === undefined) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
