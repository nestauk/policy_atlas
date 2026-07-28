import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

import { Card } from "../brand/Card";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Root render-crash surface (contract strand 14): catches an unhandled
 * render error below the app chrome so navigation stays usable, and shows
 * one honest "reload the page" message — never a stack trace. Give this a
 * `key` tied to the route so a fresh navigation gets a fresh boundary
 * instead of staying stuck in its caught state.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // No telemetry pipe wired up yet — this is the last-resort diagnostic.
    console.error("Unhandled render error", error, info);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main className="mx-auto max-w-2xl px-6 py-16">
          <Card role="alert" className="p-6">
            <h1 className="font-display text-2xl text-navy">Something went wrong</h1>
            <p className="mt-3 text-sm text-grey">Reload the page to try again.</p>
          </Card>
        </main>
      );
    }
    return this.props.children;
  }
}
