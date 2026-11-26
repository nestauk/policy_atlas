/**
 * "Your profile": edit the onboarding answers (in-app feedback, element F).
 *
 * Opened from the account menu. There is no settings page in the app, so the
 * profile has a page of its own at `/profile`.
 */
import { useState } from "react";

import { useProfile } from "../../api/feedback";
import { feedbackEnabled } from "../../lib/feedback";
import { useDocumentTitle } from "../../lib/title";
import { Card } from "../../ui/brand/Card";
import { NotFoundView } from "../../ui/feedback/NotFoundView";
import { ProfileForm } from "./ProfileForm";

/** The page at `/profile`. A 404 when the onboarding element is off. */
export function ProfileView() {
  if (!feedbackEnabled("onboarding")) return <NotFoundView />;
  return <ProfilePage />;
}

/** The page with the element on. */
function ProfilePage() {
  useDocumentTitle("Your profile");
  const profile = useProfile();
  const [saved, setSaved] = useState(false);
  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-10">
      <Card className="p-6 md:p-8">
        <h1 className="mb-8 text-title font-extrabold text-navy">Your profile</h1>
        {profile.data !== undefined && (
          // Keyed on the stored answers, so the form refills after a save.
          <ProfileForm
            key={JSON.stringify(profile.data)}
            profile={profile.data}
            submitLabel="Save"
            onSaved={() => setSaved(true)}
          />
        )}
        {profile.isError && (
          <p role="alert" className="text-body text-red">
            We could not load your profile. Reload the page.
          </p>
        )}
        <p role="status" className="mt-4 text-meta text-grey">
          {saved ? "Saved." : ""}
        </p>
      </Card>
    </main>
  );
}
