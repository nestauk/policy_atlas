import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { Button } from "../../ui/brand/Button";
import { OutlineSwitch } from "../../ui/brand/OutlineSwitch";
import { PageBackLink } from "../../ui/brand/PageHeader";
import { OpsApiError, unwrap, useOpsAction, useOrganisations } from "../api";
import { orgInRefusal } from "../format";
import {
  CHOOSE_ORGANISATION,
  CohortsField,
  Field,
  FORM_CARD_CLASS,
  FormHeader,
  INPUT_CLASS,
  OrganisationSelect,
  Panel,
  useCohortNames,
  useRecordedToast,
  withCohorts,
} from "../ui";
import { AddManyForm } from "./AddManyForm";

/** Add a person (ops-pages-copy.md § Add a person): one, or many from a file. */
export function AddPersonView() {
  const [mode, setMode] = useState<"one" | "many">("one");
  return (
    <>
      <FormHeader back={<PageBackLink to="/people">People</PageBackLink>} title="Add a person" />
      <div className="mt-6">
        <OutlineSwitch
          label="How to add"
          choices={[
            { key: "one", label: "One person" },
            { key: "many", label: "Many from a file" },
          ]}
          value={mode}
          onChange={setMode}
        />
      </div>
      <div className="mt-6 grid gap-8 md:grid-cols-[minmax(0,34rem)_minmax(0,22rem)]">
        {mode === "one" ? <OnePersonForm /> : <AddManyForm />}
        <Panel title="What happens" className="self-start">
          <div className="flex flex-col gap-3 text-body text-ink">
            {mode === "one" ? (
              <>
                <p>Policy Atlas emails them a temporary password. It is valid for 30 days.</p>
                <p>
                  If the email already has an account that is in no organisation, that account is added to this
                  organisation. No email is sent, because they can already sign in.
                </p>
                <p>If the email already belongs to another organisation, nothing changes.</p>
                <p>The person joins the cohorts you choose here.</p>
              </>
            ) : (
              <>
                <p>We check the whole file first. Nothing is created while the file has a problem.</p>
                <p>Each person gets an invitation email with a temporary password.</p>
                <p>A person who already has an account gets no second email.</p>
                <p>The people join the cohorts you choose here.</p>
                <p>We do not keep the file.</p>
              </>
            )}
          </div>
        </Panel>
      </div>
    </>
  );
}

/** One person: email, name, organisation and cohorts. */
function OnePersonForm() {
  const navigate = useNavigate();
  const toast = useRecordedToast();
  const organisations = useOrganisations();
  const cohortNames = useCohortNames();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [orgId, setOrgId] = useState("");
  const [cohortIds, setCohortIds] = useState<string[]>([]);
  const [orgMissing, setOrgMissing] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const create = useOpsAction(
    (client, body: { email: string; display_name: string; org_id: string; cohort_ids: string[] }) =>
      unwrap(client.POST("/api/v1/ops/people", { body })),
  );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (orgId === "") {
      // Required: the browser checks the two text fields; this one is ours.
      setOrgMissing(true);
      document.getElementById("person-org")?.focus();
      return;
    }
    setEmailError(null);
    setFormError(null);
    create.mutate(
      { email: email.trim(), display_name: name.trim(), org_id: orgId, cohort_ids: cohortIds },
      {
        onSuccess: (created) => {
          const org = created.person.organisation?.name ?? "";
          toast(
            withCohorts(
              created.reactivated
                ? `Reactivated and added to ${org}; they can sign in again`
                : created.invitation_sent
                  ? `Invitation sent to ${created.person.email ?? email.trim()}`
                  : `Added to ${org}, no email sent`,
              cohortNames(cohortIds),
            ),
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
            setFormError("Could not create the account. Try again.");
          }
        },
      },
    );
  };

  return (
    <form onSubmit={submit} className={FORM_CARD_CLASS}>
      <Field id="person-email" label="Email" error={emailError}>
        {(describedBy) => (
          <input
            id="person-email"
            type="email"
            required
            autoComplete="off"
            value={email}
            aria-invalid={emailError !== null}
            aria-describedby={describedBy}
            onChange={(event) => setEmail(event.target.value)}
            className={INPUT_CLASS}
          />
        )}
      </Field>
      <Field id="person-name" label="Display name">
        {(describedBy) => (
          <input
            id="person-name"
            aria-describedby={describedBy}
            required
            autoComplete="off"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className={INPUT_CLASS}
          />
        )}
      </Field>
      <Field id="person-org" label="Organisation" error={orgMissing && orgId === "" ? CHOOSE_ORGANISATION : null}>
        {(describedBy) => (
          <OrganisationSelect
            id="person-org"
            label="Organisation"
            organisations={organisations.data ?? []}
            value={orgId}
            onChange={setOrgId}
            describedBy={describedBy}
            invalid={orgMissing && orgId === ""}
          />
        )}
      </Field>
      <CohortsField id="person-cohorts" values={cohortIds} onChange={setCohortIds} />
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
  );
}
