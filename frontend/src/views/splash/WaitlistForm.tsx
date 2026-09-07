import { useId, useState, type FormEvent, type ReactNode } from "react";

import { apiBaseUrl } from "../../api/client";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { SPLASH_PROSE } from "./splashTypography";

/** Keep in sync with `policy_atlas.api.contract.waitlist`. */
export const WAITLIST_LIMITS = {
  email: 320,
  name: 200,
  organisation: 200,
  roleOrReason: 1000,
} as const;

type FormStatus = "idle" | "submitting" | "success" | "already" | "error";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function overLimitMessage(length: number, max: number): string | null {
  if (length <= max) return null;
  const over = length - max;
  return `Too long — ${over} character${over === 1 ? "" : "s"} over the ${max} limit`;
}

/**
 * Request-access form — posts to the public waitlist endpoint.
 *
 * Length limits mirror the API contract. Over-limit fields show a live
 * warning and block submit until shortened (do not silently truncate).
 */
export function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [roleOrReason, setRoleOrReason] = useState("");
  // Honeypot: hidden from humans; bots fill it and the API discards the signup.
  const [website, setWebsite] = useState("");
  const [status, setStatus] = useState<FormStatus>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [attempted, setAttempted] = useState(false);

  const emailTrim = email.trim();
  const nameTrim = name.trim();
  const orgTrim = organisation.trim();
  const roleTrim = roleOrReason.trim();

  const emailOver = email.length > WAITLIST_LIMITS.email;
  const nameOver = name.length > WAITLIST_LIMITS.name;
  const orgOver = organisation.length > WAITLIST_LIMITS.organisation;
  const roleOver = roleOrReason.length > WAITLIST_LIMITS.roleOrReason;

  const emailMissing = emailTrim.length === 0;
  const nameMissing = nameTrim.length === 0;
  const roleMissing = roleTrim.length === 0;
  const emailInvalid = !emailMissing && !EMAIL_RE.test(emailTrim.toLowerCase());

  const lengthBlocked = emailOver || nameOver || orgOver || roleOver;
  const canSubmit =
    !lengthBlocked && !emailMissing && !nameMissing && !roleMissing && !emailInvalid;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setAttempted(true);
    if (!canSubmit) {
      // Field-level errors are enough — no duplicate form summary.
      setMessage(null);
      return;
    }
    setStatus("submitting");
    setMessage(null);
    try {
      const response = await fetch(`${apiBaseUrl()}/api/v1/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: emailTrim,
          name: nameTrim,
          organisation: orgTrim || null,
          role_or_reason: roleTrim,
          website: website || null,
        }),
      });
      if (response.status === 201) {
        setStatus("success");
        setMessage("Thanks — you're on the list. We'll be in touch.");
        return;
      }
      const body = (await response.json().catch(() => null)) as {
        error?: { code?: string; message?: string };
      } | null;
      if (response.status === 409 && body?.error?.code === "already_registered") {
        setStatus("already");
        setMessage("You're already on the list with this email.");
        return;
      }
      setStatus("error");
      setMessage(body?.error?.message ?? "Something went wrong. Please try again.");
    } catch {
      setStatus("error");
      setMessage("Something went wrong. Please try again.");
    }
  };

  const done = status === "success" || status === "already";
  const disabled = done || status === "submitting";

  const emailOverMsg = overLimitMessage(email.length, WAITLIST_LIMITS.email);
  const nameOverMsg = overLimitMessage(name.length, WAITLIST_LIMITS.name);
  const orgOverMsg = overLimitMessage(organisation.length, WAITLIST_LIMITS.organisation);
  const roleOverMsg = overLimitMessage(roleOrReason.length, WAITLIST_LIMITS.roleOrReason);

  return (
    <form onSubmit={onSubmit} className="flex w-full flex-col gap-5" noValidate>
      <Field
        id="waitlist-email"
        label="Email"
        error={
          emailOverMsg ??
          (attempted && emailMissing
            ? "Enter an email address"
            : attempted && emailInvalid
              ? "Enter a valid email address"
              : null)
        }
      >
        {(describedBy, invalid) => (
          <input
            id="waitlist-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={disabled}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={fieldClass(invalid)}
          />
        )}
      </Field>

      <Field
        id="waitlist-name"
        label="Name"
        error={nameOverMsg ?? (attempted && nameMissing ? "Enter your name" : null)}
      >
        {(describedBy, invalid) => (
          <input
            id="waitlist-name"
            type="text"
            required
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={disabled}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={fieldClass(invalid)}
          />
        )}
      </Field>

      <Field
        id="waitlist-org"
        label="Organisation"
        labelExtra={<span className="font-normal text-grey">(optional)</span>}
        error={orgOverMsg}
      >
        {(describedBy, invalid) => (
          <input
            id="waitlist-org"
            type="text"
            autoComplete="organization"
            value={organisation}
            onChange={(e) => setOrganisation(e.target.value)}
            disabled={disabled}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={fieldClass(invalid)}
          />
        )}
      </Field>

      <Field
        id="waitlist-role"
        label="What would you like to use Policy Atlas for?"
        error={
          roleOverMsg ??
          (attempted && roleMissing ? "Tell us how you would use Policy Atlas" : null)
        }
      >
        {(describedBy, invalid) => (
          <textarea
            id="waitlist-role"
            required
            rows={4}
            value={roleOrReason}
            onChange={(e) => setRoleOrReason(e.target.value)}
            disabled={disabled}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            className={cn(fieldClass(invalid), "resize-y")}
          />
        )}
      </Field>

      {/* Honeypot — visually hidden and untabbable; humans never fill it. */}
      <div className="hidden" aria-hidden="true">
        <label htmlFor="waitlist-website">Website</label>
        <input
          id="waitlist-website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
        />
      </div>

      {message !== null && (
        <p
          role="status"
          className={cn(SPLASH_PROSE, status === "error" ? "text-red" : "text-navy")}
        >
          {message}
        </p>
      )}
      {!done && (
        <div>
          <Button
            type="submit"
            disabled={status === "submitting" || lengthBlocked}
            className="min-h-12 px-[22px] py-0 text-lead font-extrabold"
          >
            {status === "submitting" ? "Submitting…" : "Submit"}
          </Button>
        </div>
      )}
    </form>
  );
}

function fieldClass(invalid: boolean): string {
  return cn(
    `mt-1.5 w-full border bg-paper px-3 py-2.5 ${SPLASH_PROSE} text-navy outline-none focus:border-blue`,
    invalid ? "border-red" : "border-line",
  );
}

function Field({
  id,
  label,
  labelExtra,
  error,
  children,
}: {
  id: string;
  label: string;
  labelExtra?: ReactNode;
  error: string | null;
  children: (describedBy: string | undefined, invalid: boolean) => ReactNode;
}) {
  const uid = useId();
  const errorId = `${id}-error-${uid}`;
  const invalid = error !== null;
  const describedBy = invalid ? errorId : undefined;

  return (
    <div>
      <label htmlFor={id} className={`block ${SPLASH_PROSE} font-semibold text-navy`}>
        {label}
        {labelExtra !== undefined && <> {labelExtra}</>}
      </label>
      {children(describedBy, invalid)}
      {error !== null ? (
        <p id={errorId} role="alert" className={`mt-1.5 ${SPLASH_PROSE} text-red`}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
