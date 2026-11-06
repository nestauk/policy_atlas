import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as mutations from "../api/mutations";
import * as queries from "../api/queries";
import { ToastProvider } from "../ui/radix/Toast";
import { SHARE_COPY } from "./sharePresentation";
import { ShareView } from "./ShareView";

vi.mock("../api/queries", () => ({
  useMe: vi.fn(),
  useProjects: vi.fn(),
  useTask: vi.fn(),
}));

vi.mock("../api/mutations", () => ({
  useUpdateTask: vi.fn(),
}));

const TASK_ID = "11111111-1111-1111-1111-111111111111";
const PROJECT_A = "60000000-0000-4000-8000-000000000001";
const PROJECT_B = "60000000-0000-4000-8000-000000000002";
const ORG = { org_id: "org-1", name: "Department for Local Growth" };

function baseTask(overrides: Record<string, unknown> = {}) {
  return {
    task_id: TASK_ID,
    name: "A task",
    visibility: "private",
    is_owner: true,
    is_public: false,
    project_ids: [],
    owner_display: "Ada Lovelace",
    ...overrides,
  };
}

function setup({
  task = {},
  organisation = null,
  projects = [],
  mutate = vi.fn(),
}: {
  task?: Record<string, unknown>;
  organisation?: typeof ORG | null;
  projects?: { project_id: string; name: string }[];
  mutate?: ReturnType<typeof vi.fn>;
} = {}) {
  vi.mocked(queries.useMe).mockReturnValue({
    data: { user_id: "u1", display_name: "Ada Lovelace", organisation, is_admin: false },
  } as unknown as ReturnType<typeof queries.useMe>);
  vi.mocked(queries.useProjects).mockReturnValue(
    { data: { data: projects }, isPending: false } as unknown as ReturnType<typeof queries.useProjects>,
  );
  vi.mocked(queries.useTask).mockReturnValue({ data: baseTask(task) } as unknown as ReturnType<typeof queries.useTask>);
  vi.mocked(mutations.useUpdateTask).mockReturnValue(
    { mutate, isPending: false } as unknown as ReturnType<typeof mutations.useUpdateTask>,
  );
  render(
    <ToastProvider>
      <MemoryRouter initialEntries={[`/tasks/${TASK_ID}/share`]}>
        <Routes>
          <Route path="/tasks/:taskId/share" element={<ShareView />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  );
  return { mutate, user: userEvent.setup() };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("ShareView — layout (round 10, S1, S2, S10)", () => {
  it("names the page and orders the sections Public link, Organisation, Projects", () => {
    setup({ organisation: ORG });
    expect(screen.getByRole("heading", { level: 1, name: "Share" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent)).toEqual([
      SHARE_COPY.publicHeading,
      SHARE_COPY.orgHeading,
      SHARE_COPY.projectsHeading,
    ]);
  });

  it("carries no blue cut-corner fill: every control is the 40 px outline or ghost", () => {
    setup({ organisation: ORG, task: { is_public: true }, projects: [{ project_id: PROJECT_A, name: "Net zero homes" }] });
    for (const button of screen.getAllByRole("button")) {
      expect(button.className).not.toMatch(/\bcutout\b|\bbg-blue\b/);
      expect(button).toHaveClass("h-10");
    }
  });
});

describe("ShareView — public link (task 037, contract § R1; round 10, S3)", () => {
  it("asks once more before making the task public, and Keep private changes nothing", async () => {
    const { mutate, user } = setup();
    expect(screen.getByText(SHARE_COPY.publicOff)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: SHARE_COPY.makePublic }));
    const step = screen.getByRole("group", { name: SHARE_COPY.confirmPublic });
    expect(within(step).getByText(SHARE_COPY.confirmPublic)).toHaveFocus();
    expect(mutate).not.toHaveBeenCalled();
    await user.click(within(step).getByRole("button", { name: SHARE_COPY.keepPrivate }));
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it("issues a PATCH {is_public: true} on the second press", async () => {
    const { mutate, user } = setup();
    await user.click(screen.getByRole("button", { name: SHARE_COPY.makePublic }));
    await user.click(within(screen.getByRole("group")).getByRole("button", { name: SHARE_COPY.makePublic }));
    expect(mutate).toHaveBeenCalledWith({ is_public: true }, expect.anything());
  });

  it("shows the public link in a read-only field and says Copied beside the button, no toast", async () => {
    const { user } = setup({ task: { is_public: true } });
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    expect(screen.getByText(SHARE_COPY.publicOn)).toBeInTheDocument();
    const field = screen.getByRole("textbox", { name: SHARE_COPY.linkField });
    expect(field).toHaveAttribute("readonly");
    expect((field as HTMLInputElement).value).toMatch(new RegExp(`/tasks/${TASK_ID}/result$`));

    await user.click(screen.getByRole("button", { name: SHARE_COPY.copyLink }));

    expect(writeText).toHaveBeenCalledWith(expect.stringMatching(new RegExp(`/tasks/${TASK_ID}/result$`)));
    expect(await screen.findByText(SHARE_COPY.copied)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: SHARE_COPY.stopPublic })).toBeInTheDocument();
  });

  it("selects the link when the copy fails and says so", async () => {
    const { user } = setup({ task: { is_public: true } });
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
    await user.click(screen.getByRole("button", { name: SHARE_COPY.copyLink }));
    expect(await screen.findByText(SHARE_COPY.copyFailed)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: SHARE_COPY.linkField })).toHaveFocus();
  });

  it("shows a colleague the public state without a control (S8)", () => {
    setup({ task: { is_owner: false, is_public: true } });
    expect(screen.getByText(SHARE_COPY.publicOn)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: SHARE_COPY.stopPublic })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});

describe("ShareView — organisation (round 10, S4, S6)", () => {
  it("offers the owner Make private outside a project", async () => {
    const mutate = vi.fn();
    const { user } = setup({ organisation: ORG, task: { visibility: "org" }, mutate });
    expect(screen.getByText(SHARE_COPY.orgShared)).toHaveClass("font-semibold", "text-navy");
    await user.click(screen.getByRole("button", { name: SHARE_COPY.makePrivate }));
    expect(mutate).toHaveBeenCalledWith({ visibility: "private" }, expect.anything());
  });

  it("does not offer Make private while the task is in a project, and names the project", () => {
    setup({
      organisation: ORG,
      task: { visibility: "org", project_ids: [PROJECT_A] },
      projects: [{ project_id: PROJECT_A, name: "Net zero homes" }],
    });
    expect(screen.queryByRole("button", { name: SHARE_COPY.makePrivate })).not.toBeInTheDocument();
    const note = screen.getByText(/Follows its project:/);
    expect(note).toHaveTextContent("Follows its project: Net zero homes.");
    expect(within(note).getByRole("link", { name: "Net zero homes" })).toHaveAttribute("href", `/projects/${PROJECT_A}`);
  });
});

describe("ShareView — projects (round 10, S5, S8)", () => {
  it("gives the owner Remove and Add", () => {
    setup({
      task: { project_ids: [PROJECT_A] },
      projects: [
        { project_id: PROJECT_A, name: "Net zero homes" },
        { project_id: PROJECT_B, name: "School food" },
      ],
    });
    expect(screen.getByRole("button", { name: SHARE_COPY.remove })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: SHARE_COPY.addToProject })).toBeInTheDocument();
  });

  // Round 12: the app's dropdown; a pick adds the project and the control
  // goes back to its placeholder.
  it("adds the project picked from the app's dropdown and offers only the others", async () => {
    const { user, mutate: updateMutate } = setup({
      task: { project_ids: [PROJECT_A] },
      projects: [
        { project_id: PROJECT_A, name: "Net zero homes" },
        { project_id: PROJECT_B, name: "School food" },
      ],
    });
    const add = screen.getByRole("combobox", { name: SHARE_COPY.addToProject });
    expect(add.tagName).toBe("BUTTON");
    expect(add).toHaveTextContent(SHARE_COPY.selectProject);
    await user.click(add);
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual(["School food"]);
    await user.click(screen.getByRole("option", { name: "School food" }));
    expect(updateMutate).toHaveBeenCalled();
    expect(JSON.stringify(updateMutate.mock.calls.at(-1)?.[0])).toContain(PROJECT_B);
  });

  it("does not show Remove or Add to a colleague, only the project links", () => {
    setup({
      task: { is_owner: false, project_ids: [PROJECT_A] },
      projects: [
        { project_id: PROJECT_A, name: "Net zero homes" },
        { project_id: PROJECT_B, name: "School food" },
      ],
    });
    expect(screen.getByRole("link", { name: "Net zero homes" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: SHARE_COPY.remove })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("shows the server's message when a change is refused", async () => {
    const mutate = vi.fn((_body: unknown, options: { onError: (error: unknown) => void }) =>
      options.onError({ code: "forbidden", message: "Only the task's owner can change its projects." }),
    );
    const { user } = setup({
      task: { project_ids: [PROJECT_A] },
      projects: [{ project_id: PROJECT_A, name: "Net zero homes" }],
      mutate,
    });
    await user.click(screen.getByRole("button", { name: SHARE_COPY.remove }));
    expect(screen.getByRole("alert")).toHaveTextContent("Only the task's owner can change its projects.");
  });

  it("falls back to its own sentence when the refusal carries no message", async () => {
    const mutate = vi.fn((_body: unknown, options: { onError: (error: unknown) => void }) =>
      options.onError({ code: "forbidden", message: "action is not permitted" }),
    );
    const { user } = setup({
      task: { project_ids: [PROJECT_A] },
      projects: [{ project_id: PROJECT_A, name: "Net zero homes" }],
      mutate,
    });
    await user.click(screen.getByRole("button", { name: SHARE_COPY.remove }));
    expect(screen.getByRole("alert")).toHaveTextContent(SHARE_COPY.projectsFailed);
  });

  it("points to Projects when the owner has none to add to (P5)", () => {
    setup();
    const line = screen.getByText(/Not in a project\./);
    expect(line).toHaveTextContent("Not in a project. Create one in Projects.");
    expect(within(line).getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/projects");
  });
});
