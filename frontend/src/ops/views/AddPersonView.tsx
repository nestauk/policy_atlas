import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { Button } from "../../ui/brand/Button";
import { PageBackLink, PageHeader } from "../../ui/brand/PageHeader";
import { OpsApiError, unwrap, useOpsAction, useOrganisations } from "../api";
import { orgInRefusal, productDomain } from "../format";
import { Field, INPUT_CLASS, OrganisationSelect, Panel, useRecordedToast } from "../ui";

/** Add a person (ops-pages-copy.md § Add a person): create in an organisation. */
export function AddPersonView() {
  const navigate = useNavigate();
  const toast = useRecordedToast();
  const organisations = useOrganisations();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [orgId, setOrgId] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const create = useOpsAction((client, body: { email: string; display_name: string; org_id: string }) =>
    unwrap(client.POST("/api/v1/ops/people", { body })),
  );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (orgId === "") {
      // Required: the browser checks the two text fields; this one is ours.
      document.getElementById("person-org")?.focus();
      return;
    }
    setEmailError(null);
    setFormError(null);
    create.mutate(
      { email: email.trim(), display_name: name.trim(), org_id: orgId },
      {
        onSuccess: (created) => {
          const org = created.person.organisation?.name ?? "";
          toast(
            created.invitation_sent
              ? `Invitation sent to ${created.person.email ?? email.trim()}`
              : `Added to ${org}, no email sent`,
          );
          navigate("/people");
        },
        onError: (error) => {
          if (error instanceof OpsApiError && error.code === "enrolled_elsewhere") {
            const org = orgInRefusal(error.message);
            setEmailError(
              org === null ? error.message : `Already in ${org}. Use Enrol or move from the People list.`,
            );
          } else if (error instanceof OpsApiError && error.code === "ops_refused") {
            setFormError(error.message);
          } else {
            setFormError("Something went wrong. Try again.");
          }
        },
      },
    );
  };

  return (
    <>
      <PageHeader
        context={<PageBackLink to="/people">People</PageBackLink>}
        title="Add a person"
        actions={null}
      />
      <div className="mt-6 grid gap-8 md:grid-cols-[minmax(0,34rem)_minmax(0,22rem)]">
        <form onSubmit={submit} className="flex flex-col gap-6 border border-line-2 bg-paper p-6 shadow-paper max-md:p-4">
          <Field id="person-email" label="Email" error={emailError}>
            <input
              id="person-email"
              type="email"
              required
              autoComplete="off"
              value={email}
              aria-invalid={emailError !== null}
              aria-describedby={emailError !== null ? "person-email-error" : undefined}
              onChange={(event) => setEmail(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field id="person-name" label="Display name" help="Shown to colleagues. Not the email.">
            <input
              id="person-name"
              required
              autoComplete="off"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className={INPUT_CLASS}
            />
          </Field>
          <Field id="person-org" label="Organisation">
            <OrganisationSelect
              id="person-org"
              label="Organisation"
              organisations={organisations.data ?? []}
              value={orgId}
              onChange={setOrgId}
            />
          </Field>
          {formError !== null && (
            <p role="alert" className="text-body text-red">
              {formError}
            </p>
          )}
          <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => navigate("/people")}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              Create and send invitation
            </Button>
          </div>
        </form>
        <Panel title="What happens" className="self-start">
          <div className="flex flex-col gap-3 text-body text-ink">
            <p>
              Cognito creates the account and emails a temporary password from no-reply@{productDomain()}. It is valid
              for 30 days.
            </p>
            <p>If the address already has an account with no organisation, it is added to this one and no email is sent.</p>
            <p>If it already belongs to another organisation, nothing changes and you are told which one.</p>
          </div>
        </Panel>
      </div>
    </>
  );
}
