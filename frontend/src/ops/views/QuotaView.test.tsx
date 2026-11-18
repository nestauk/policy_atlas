import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { POLICY_LAB } from "../mock/fixtures";
import { opsMock } from "../mock";
import { renderOps, withOpsMock } from "../testing";

withOpsMock();

describe("Set a quota", () => {
  it("shows a person's facts, the inherited placeholders, the warning and the limits that apply", async () => {
    renderOps("/people/sub-tom/quota");
    expect(await screen.findByRole("heading", { name: "Quota for Tom Ellis" })).toBeInTheDocument();
    expect(screen.getByText("Nesta · 12 tasks created in the last 365 days")).toBeInTheDocument();
    expect(screen.getByLabelText("Tasks per year")).toHaveAttribute("placeholder", "Inherits Nesta · 100");
    expect(screen.getByLabelText("Simultaneous tasks")).toHaveAttribute("placeholder", "Inherits the default · 3");
    expect(screen.getByText("Leave empty to inherit. Enter 0 for no limit.")).toBeInTheDocument();
    const warning = screen.getByText(/this limit protects the shared run capacity/).closest("p") as HTMLElement;
    expect(warning).toHaveTextContent(
      "Warning: this limit protects the shared run capacity. A higher number lets this person take more of it at the same time, which can slow other people's runs.",
    );
    expect(warning).toHaveClass("bg-yellow-tint");
    const limits = screen.getByRole("region", { name: "Currently applied limits" });
    expect(limits).toHaveTextContent("Tasks per year: 100 · from Nesta");
    expect(limits).toHaveTextContent("Simultaneous tasks: 3 · from the default");
    expect(limits).toHaveTextContent("Admin exemption: no");
  });

  it("saves the numbers, and Clear and inherit sends nulls", async () => {
    const user = userEvent.setup();
    renderOps("/people/sub-mara/quota");
    const runs = await screen.findByLabelText("Simultaneous tasks");
    expect(runs).toHaveValue("6");
    expect(within(screen.getByRole("region", { name: "Currently applied limits" })).getByText(/Tasks per year: no limit · from this person/)).toBeInTheDocument();
    await user.clear(runs);
    await user.type(runs, "8");
    await user.click(screen.getByRole("button", { name: "Save quota" }));
    expect(await screen.findByText("Quota saved · recorded")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)).toMatchObject({
      path: "/api/v1/ops/people/quota",
      body: { user_ids: ["sub-mara"], task_quota_per_year: 0, runs_per_user: 8 },
    });
    await user.click(screen.getByRole("button", { name: "Clear and inherit" }));
    await screen.findAllByText("Quota saved · recorded");
    expect(opsMock.writes.at(-1)?.body).toEqual({ user_ids: ["sub-mara"], task_quota_per_year: null, runs_per_user: null });
    expect(screen.getByLabelText("Simultaneous tasks")).toHaveValue("");
  });

  it("refuses a value that is not a whole number, and sends nothing", async () => {
    const user = userEvent.setup();
    renderOps("/people/sub-mara/quota");
    const runs = await screen.findByLabelText("Simultaneous tasks");
    await user.clear(runs);
    await user.type(runs, "1e");
    const tasks = screen.getByLabelText("Tasks per year");
    await user.type(tasks, "2.5");
    await user.click(screen.getByRole("button", { name: "Save quota" }));
    expect(screen.getAllByText("Enter a whole number, or leave it empty.")).toHaveLength(2);
    expect(runs).toHaveAttribute("aria-invalid", "true");
    expect(runs).toHaveAccessibleDescription(/Enter a whole number, or leave it empty\.$/);
    expect(opsMock.writes).toEqual([]);
    await user.clear(runs);
    await user.type(runs, "4");
    await user.clear(tasks);
    await user.click(screen.getByRole("button", { name: "Save quota" }));
    expect(await screen.findByText("Quota saved · recorded")).toBeInTheDocument();
    expect(screen.queryByText("Enter a whole number, or leave it empty.")).toBeNull();
    expect(opsMock.writes.at(-1)?.body).toEqual({ user_ids: ["sub-mara"], task_quota_per_year: null, runs_per_user: 4 });
  });

  it("an organisation's form says who it applies to and inherits the defaults", async () => {
    const user = userEvent.setup();
    renderOps(`/organisations/${POLICY_LAB}/quota`);
    expect(await screen.findByRole("heading", { name: "Quota for Policy Lab" })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByRole("link", { name: "Organisations" })).toBeInTheDocument();
    expect(screen.getByText("Applies to everyone in Policy Lab who has no number of their own.")).toBeInTheDocument();
    expect(screen.getByLabelText("Tasks per year")).toHaveAttribute("placeholder", "Inherits the default · 50");
    expect(screen.getByLabelText("Simultaneous tasks")).toHaveValue("5");
    expect(screen.getByLabelText("Simultaneous tasks")).toHaveAccessibleDescription(
      "Warning: this limit protects the shared run capacity. A higher number lets each person in Policy Lab take more of it at the same time, which can slow other people's runs.",
    );
    expect(screen.getByLabelText("Tasks per year")).toHaveAccessibleDescription("Leave empty to inherit. Enter 0 for no limit.");
    await user.click(screen.getByRole("button", { name: "Clear and inherit" }));
    expect(await screen.findByText("Quota saved · recorded")).toBeInTheDocument();
    expect(opsMock.writes.at(-1)).toEqual({
      method: "POST",
      path: `/api/v1/ops/organisations/${POLICY_LAB}/quota`,
      body: { task_quota_per_year: null, runs_per_user: null },
    });
  });
});
