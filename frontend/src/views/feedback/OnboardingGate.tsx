/**
 * The onboarding gate (in-app feedback, element F).
 *
 * At first access the profile form takes the whole screen in place of the
 * app, before the first task. `lib/profileGate.ts` holds the rules. The gate
 * does nothing when the `onboarding` element is off.
 */
import { useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router";

import { useProfile, useSkipProfile } from "../../api/feedback";
import { useAuth } from "../../auth";
import { feedbackEnabled } from "../../lib/feedback";
import { forgetSkipped, markSkipped, profileGate, skippedThisSession } from "../../lib/profileGate";
import { Card } from "../../ui/brand/Card";
import { PROSE_LINK_CLASS } from "../../ui/brand/inlineActions";
import { NavBar, NavHomeLink } from "../../ui/brand/Nav";
import { TooltipProvider } from "../../ui/radix/Tooltip";
import { ProfileForm } from "./ProfileForm";

/** A person who is asked for personal data can read these pages first. */
const UNGATED_PATHS = new Set(["/privacy", "/terms"]);

/**
 * Show the profile form in place of the app while the profile is due.
 *
 * Args:
 *   children: The app.
 */
export function OnboardingGate({ children }: { children: ReactNode }) {
  if (!feedbackEnabled("onboarding")) return <>{children}</>;
  return <ActiveGate>{children}</ActiveGate>;
}

/** The gate with the element on: reads the profile and applies the rules. */
function ActiveGate({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();
  const profile = useProfile();
  const skip = useSkipProfile();
  const userId = auth.user?.sub ?? "";
  const [skipped, setSkipped] = useState(() => skippedThisSession(userId));

  const gate = profileGate(profile.data, skipped);
  if (gate === "pass" || UNGATED_PATHS.has(location.pathname)) return <>{children}</>;

  const onSkip = () =>
    skip.mutate(undefined, {
      onSuccess: () => {
        markSkipped(userId);
        setSkipped(true);
      },
    });

  return (
    // The form replaces the app shell, so it brings the provider that the
    // logo's hint needs.
    <TooltipProvider delayDuration={200}>
    <div className="flex min-h-svh flex-col bg-ground">
      <NavBar aria-label="App">
        <NavHomeLink />
        <button
          type="button"
          className="ml-auto min-h-11 cursor-pointer text-meta font-semibold text-navy hover:text-blue"
          onClick={() => {
            forgetSkipped();
            void auth.signOut();
          }}
        >
          Sign out
        </button>
      </NavBar>
      <main className="mx-auto w-full max-w-2xl px-4 py-10">
        <Card className="p-6 md:p-8">
          <h1 className="text-title font-extrabold text-navy">Before you start</h1>
          <p className="mt-2 mb-8 text-body text-grey">
            Four short questions help us to understand who uses Policy Atlas and for what
            work. Read the{" "}
            <Link to="/privacy" className={PROSE_LINK_CLASS}>
              privacy notice
            </Link>
            .
          </p>
          <ProfileForm
            submitLabel="Continue"
            onSkip={gate === "ask" ? onSkip : undefined}
            skipping={skip.isPending}
          />
        </Card>
      </main>
    </div>
    </TooltipProvider>
  );
}
