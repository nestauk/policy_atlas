import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../radix/Toast";
import { ReportIssueButton } from "./ReportIssueButton";
import * as mutations from "../../api/mutations";

vi.mock("../../api/mutations", () => ({ useReportIssue: vi.fn() }));

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";
const reportIssue = vi.fn();

function renderButton() {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[`/projects/${PROJECT_ID}/sources`]}>
        <ReportIssueButton projectId={PROJECT_ID} />
      </MemoryRouter>
    </ToastProvider>,
  );
}

beforeEach(() => {
  reportIssue.mockReset();
  reportIssue.mockImplementation((_input, options) => options?.onSuccess?.());
  vi.mocked(mutations.useReportIssue).mockReturnValue(
    { mutate: reportIssue, isPending: false } as unknown as ReturnType<typeof mutations.useReportIssue>,
  );
});

describe("ReportIssueButton (032)", () => {
  it("keeps submit inert until there is real text", async () => {
    const user = userEvent.setup();
    renderButton();
    await user.click(screen.getByRole("button", { name: "Report an issue" }));
    const submit = screen.getByRole("button", { name: "Send report" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("What did you notice?"), "   ");
    expect(screen.getByRole("button", { name: "Send report" })).toBeDisabled();
  });

  it("sends the trimmed text with the current page path, then clears and closes", async () => {
    const user = userEvent.setup();
    renderButton();
    await user.click(screen.getByRole("button", { name: "Report an issue" }));
    await user.type(screen.getByLabelText("What did you notice?"), "  the year column is empty  ");
    await user.click(screen.getByRole("button", { name: "Send report" }));

    expect(reportIssue).toHaveBeenCalledTimes(1);
    expect(reportIssue.mock.calls[0][0]).toEqual({
      body: "the year column is empty",
      pagePath: `/projects/${PROJECT_ID}/sources`,
    });
    expect(await screen.findByText("Thank you — that's been logged")).toBeInTheDocument();
    expect(screen.queryByLabelText("What did you notice?")).toBeNull();

    // Reopening starts from an empty box — the sent text is not left behind.
    await user.click(screen.getByRole("button", { name: "Report an issue" }));
    expect(screen.getByLabelText("What did you notice?")).toHaveValue("");
  });

  it("keeps the text and shows an inline alert when the send fails", async () => {
    const user = userEvent.setup();
    reportIssue.mockImplementation((_input, options) => options?.onError?.(new Error("boom")));
    renderButton();
    await user.click(screen.getByRole("button", { name: "Report an issue" }));
    const box = screen.getByLabelText("What did you notice?");
    await user.type(box, "sorting is wrong");
    await user.click(screen.getByRole("button", { name: "Send report" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Your text is still here");
    expect(screen.getByLabelText("What did you notice?")).toHaveValue("sorting is wrong");
  });

  it("drops a stale failure notice when the sheet is closed and reopened", async () => {
    const user = userEvent.setup();
    reportIssue.mockImplementation((_input, options) => options?.onError?.(new Error("boom")));
    renderButton();
    await user.click(screen.getByRole("button", { name: "Report an issue" }));
    await user.type(screen.getByLabelText("What did you notice?"), "sorting is wrong");
    await user.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Report an issue" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
