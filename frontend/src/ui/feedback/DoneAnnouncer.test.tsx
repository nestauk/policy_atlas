import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DoneAnnouncer } from "./DoneAnnouncer";

describe("DoneAnnouncer", () => {
  it("is an empty status region until the work ends, then says so, and clears when work starts again", () => {
    const view = render(<DoneAnnouncer busy={false} words="The Agent replied" />);
    const status = screen.getByRole("status");
    expect(status).toBeEmptyDOMElement();
    view.rerender(<DoneAnnouncer busy words="The Agent replied" />);
    expect(status).toBeEmptyDOMElement();
    view.rerender(<DoneAnnouncer busy={false} words="The Agent replied" />);
    expect(status).toHaveTextContent("The Agent replied");
    view.rerender(<DoneAnnouncer busy words="The Agent replied" />);
    expect(status).toBeEmptyDOMElement();
  });
});
