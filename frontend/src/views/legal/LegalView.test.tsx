import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { PrivacyView } from "./PrivacyView";
import { TermsView } from "./TermsView";

describe("Privacy notice", () => {
  it("renders the notice, DPO contact, vendor privacy links, and the analytics, waitlist and email wording", () => {
    render(
      <MemoryRouter>
        <PrivacyView />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Privacy notice" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "dpo@nesta.org.uk" })).toHaveAttribute(
      "href",
      "mailto:dpo@nesta.org.uk",
    );
    expect(screen.getByRole("link", { name: "Amazon Web Services privacy policy" })).toHaveAttribute(
      "href",
      "https://aws.amazon.com/privacy/",
    );
    expect(screen.queryByText(/OpenAI:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Clerk/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Supabase/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "PostHog's privacy notice" })).toHaveAttribute(
      "href",
      "https://posthog.com/privacy",
    );
    expect(screen.getByText("Last updated: 25/11/2026")).toBeInTheDocument();
    expect(screen.getByText(/we add you to our waitlist/)).toBeInTheDocument();
    expect(screen.getByText(/Every product update has an unsubscribe link/)).toBeInTheDocument();
    expect(screen.getByText(/record the IP address/)).toBeInTheDocument();
  });
});

describe("Terms of use", () => {
  it("renders the terms, last-updated date, and Nesta charity numbers", () => {
    render(
      <MemoryRouter>
        <TermsView />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Terms of use" })).toBeInTheDocument();
    expect(screen.getByText("Last updated: 25/11/2026")).toBeInTheDocument();
    expect(screen.getByText(/1144091/)).toBeInTheDocument();
    expect(screen.getByText(/SC042833/)).toBeInTheDocument();
    expect(screen.getByText(/The courts of England and Wales have exclusive jurisdiction/)).toBeInTheDocument();
    expect(screen.getByText(/managed via Amazon Cognito/)).toBeInTheDocument();
    expect(screen.getByText(/Amazon Cognito: For user authentication/)).toBeInTheDocument();
    expect(screen.getByText(/Amazon Aurora PostgreSQL: For database management/)).toBeInTheDocument();
    expect(screen.getByText(/Amazon Bedrock: For text generation and summarisation/)).toBeInTheDocument();
    expect(screen.queryByText(/OpenAI:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Clerk/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Supabase/)).not.toBeInTheDocument();
  });
});
