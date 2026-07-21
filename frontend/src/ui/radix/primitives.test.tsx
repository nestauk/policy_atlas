import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Button } from "../brand/Button";
import { Popover, PopoverContent, PopoverTrigger } from "./Popover";
import { Sheet, SheetContent, SheetTrigger } from "./Sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./Tabs";
import { ToastProvider, useToast } from "./Toast";
import { Tooltip, TooltipProvider } from "./Tooltip";

describe("Sheet", () => {
  it("opens from its trigger, traps focus, and closes on Escape", async () => {
    render(
      <Sheet>
        <SheetTrigger asChild>
          <Button variant="secondary">Open dossier</Button>
        </SheetTrigger>
        <SheetContent title="Source dossier">
          <p>Dossier body</p>
        </SheetContent>
      </Sheet>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Open dossier" }));
    expect(screen.getByRole("dialog", { name: "Source dossier" })).toBeInTheDocument();
    expect(screen.getByText("Dossier body")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("Popover", () => {
  it("opens on click and dismisses on Escape", async () => {
    render(
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="ghost">Citation 3</Button>
        </PopoverTrigger>
        <PopoverContent>Quoted passage context</PopoverContent>
      </Popover>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Citation 3" }));
    expect(screen.getByText("Quoted passage context")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByText("Quoted passage context")).not.toBeInTheDocument();
  });
});

describe("Tabs", () => {
  it("switches panels with arrow keys", async () => {
    render(
      <Tabs defaultValue="findings">
        <TabsList aria-label="Workspace views">
          <TabsTrigger value="findings">Findings</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>
        <TabsContent value="findings">Findings panel</TabsContent>
        <TabsContent value="sources">Sources panel</TabsContent>
      </Tabs>,
    );
    expect(screen.getByText("Findings panel")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Findings" }));
    await userEvent.keyboard("{ArrowRight}");
    expect(await screen.findByText("Sources panel")).toBeInTheDocument();
    expect(screen.queryByText("Findings panel")).not.toBeInTheDocument();
  });
});

describe("Tooltip", () => {
  it("shows content on focus", async () => {
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip content="Grounded quote">
          <Button variant="ghost">[1]</Button>
        </Tooltip>
      </TooltipProvider>,
    );
    await userEvent.tab();
    expect(await screen.findAllByText("Grounded quote")).not.toHaveLength(0);
  });
});

function ToastHarness() {
  const { toast } = useToast();
  return (
    <Button
      variant="secondary"
      onClick={() => {
        toast({ title: "Something went wrong", description: "Try again", tone: "error" });
      }}
    >
      Trigger
    </Button>
  );
}

describe("Toast", () => {
  it("announces and dismisses", async () => {
    render(
      <ToastProvider>
        <ToastHarness />
      </ToastProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Trigger" }));
    expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});
