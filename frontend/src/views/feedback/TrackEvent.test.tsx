import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TrackAction, TrackEvent } from "./TrackEvent";

const state = vi.hoisted(() => ({ track: vi.fn(), useTrackEvent: vi.fn() }));
vi.mock("../../api/feedback", () => ({
  useTrackEvent: () => {
    state.useTrackEvent();
    return state.track;
  },
}));

beforeEach(() => {
  vi.stubEnv("VITE_FEEDBACK", "analytics");
  state.track.mockReset();
  state.useTrackEvent.mockReset();
});
afterEach(() => vi.unstubAllEnvs());

describe("TrackEvent", () => {
  it("sends the page event once when the page opens", () => {
    const view = render(<TrackEvent event="report_opened" taskId="task-1" />);
    view.rerender(<TrackEvent event="report_opened" taskId="task-1" />);

    expect(state.track).toHaveBeenCalledOnce();
    expect(state.track).toHaveBeenCalledWith("report_opened", "task-1");
  });

  it("sends it again for another task", () => {
    const view = render(<TrackEvent event="report_opened" taskId="task-1" />);
    view.rerender(<TrackEvent event="report_opened" taskId="task-2" />);

    expect(state.track).toHaveBeenCalledTimes(2);
  });

  it("does nothing, and does not touch the API client, with analytics off", () => {
    vi.stubEnv("VITE_FEEDBACK", "onboarding");

    render(<TrackEvent event="report_opened" taskId="task-1" />);

    expect(state.useTrackEvent).not.toHaveBeenCalled();
    expect(state.track).not.toHaveBeenCalled();
  });
});

describe("TrackAction", () => {
  const exportButton = (onAction: () => void) => (
    <button type="button" onClick={onAction}>
      Export
    </button>
  );

  it("reports the action when it happens, not when the control renders", async () => {
    const user = userEvent.setup();
    render(
      <TrackAction event="report_exported" taskId="task-1">
        {exportButton}
      </TrackAction>,
    );
    expect(state.track).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Export" }));

    expect(state.track).toHaveBeenCalledWith("report_exported", "task-1");
  });

  it("still renders the control, and reports nothing, with analytics off", async () => {
    vi.stubEnv("VITE_FEEDBACK", "");
    const user = userEvent.setup();
    render(
      <TrackAction event="report_exported" taskId="task-1">
        {exportButton}
      </TrackAction>,
    );

    await user.click(screen.getByRole("button", { name: "Export" }));

    expect(state.useTrackEvent).not.toHaveBeenCalled();
    expect(state.track).not.toHaveBeenCalled();
  });
});
