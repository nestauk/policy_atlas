import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as mutations from "../api/mutations";
import * as queries from "../api/queries";
import { PUBLIC_SHARE } from "../lib/vocabulary";
import { ToastProvider } from "../ui/radix/Toast";
import { ShareView } from "./ShareView";

vi.mock("../api/queries", () => ({
  useMe: vi.fn(),
  usePortfolios: vi.fn(),
  useProject: vi.fn(),
}));

vi.mock("../api/mutations", () => ({
  useUpdateProject: vi.fn(),
}));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";

function baseProject(overrides: Record<string, unknown> = {}) {
  return {
    project_id: PROJECT_ID,
    name: "A task",
    visibility: "private",
    is_owner: true,
    is_public: false,
    portfolio_ids: [],
    ...overrides,
  };
}

function renderShare() {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/share`]}>
        <Routes>
          <Route path="/projects/:projectId/share" element={<ShareView />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.mocked(queries.useMe).mockReturnValue(
    { data: { user_id: "u1", display_name: "Ada Lovelace", organisation: null, is_admin: false } } as unknown as ReturnType<
      typeof queries.useMe
    >,
  );
  vi.mocked(queries.usePortfolios).mockReturnValue(
    { data: { data: [] }, isPending: false } as unknown as ReturnType<typeof queries.usePortfolios>,
  );
});

describe("ShareView — public link section (task 037, contract § R1)", () => {
  it("shows the Public link section to the owner", () => {
    vi.mocked(queries.useProject).mockReturnValue(
      { data: baseProject() } as unknown as ReturnType<typeof queries.useProject>,
    );
    vi.mocked(mutations.useUpdateProject).mockReturnValue(
      { mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
    );

    renderShare();

    expect(screen.getByText(PUBLIC_SHARE.heading)).toBeInTheDocument();
    expect(screen.getByText(PUBLIC_SHARE.warning)).toBeInTheDocument();
    expect(screen.getByText(PUBLIC_SHARE.statusOff)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: PUBLIC_SHARE.turnOn })).toBeInTheDocument();
  });

  it("hides the Public link section from a non-owner", () => {
    vi.mocked(queries.useProject).mockReturnValue(
      { data: baseProject({ is_owner: false }) } as unknown as ReturnType<typeof queries.useProject>,
    );
    vi.mocked(mutations.useUpdateProject).mockReturnValue(
      { mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
    );

    renderShare();

    expect(screen.queryByText(PUBLIC_SHARE.heading)).not.toBeInTheDocument();
  });

  it("issues a PATCH {is_public: true} when the owner turns sharing on", async () => {
    vi.mocked(queries.useProject).mockReturnValue(
      { data: baseProject() } as unknown as ReturnType<typeof queries.useProject>,
    );
    const mutate = vi.fn();
    vi.mocked(mutations.useUpdateProject).mockReturnValue(
      { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
    );

    const user = userEvent.setup();
    renderShare();
    await user.click(screen.getByRole("button", { name: PUBLIC_SHARE.turnOn }));

    expect(mutate).toHaveBeenCalledWith({ is_public: true }, expect.anything());
  });

  it("copies the public results URL when sharing is on", async () => {
    vi.mocked(queries.useProject).mockReturnValue(
      { data: baseProject({ is_public: true }) } as unknown as ReturnType<typeof queries.useProject>,
    );
    vi.mocked(mutations.useUpdateProject).mockReturnValue(
      { mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof mutations.useUpdateProject>,
    );

    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    renderShare();
    await user.click(screen.getByRole("button", { name: PUBLIC_SHARE.copyLink }));

    expect(writeText).toHaveBeenCalledWith(expect.stringMatching(new RegExp(`/projects/${PROJECT_ID}/results$`)));
    expect(await screen.findByText(PUBLIC_SHARE.copied)).toBeInTheDocument();
  });
});
