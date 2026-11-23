import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import { apiBaseUrl } from "../../api/client";
import { Button } from "../../ui/brand/Button";
import { cn } from "../../ui/brand/cn";
import { SPLASH_PROSE } from "./splashTypography";
import { useWafCaptcha } from "./wafCaptcha";

/** Keep in sync with `policy_atlas.api.contract.waitlist`. */
export const WAITLIST_LIMITS = {
  email: 320,
  name: 200,
  organisation: 200,
  roleOrReason: 1000,
} as const;

type FormStatus = "idle" | "submitting" | "success" | "error";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function overLimitMessage(length: number, max: number): string | null {
  if (length <= max) return null;
  const over = length - max;
  return `Too long — ${over} character${over === 1 ? "" : "s"} over the ${max} limit`;
}

/**
 * Request-access form — posts to the public waitlist endpoint.
 *
 * Length limits mirror the API contract. An over-limit field shows a warning
 * as it is typed and counts as an error on submit (do not silently truncate).
 *
 * Submit stays enabled, so it can take focus and say what is wrong: a failed
 * submit moves focus to the first field with an error, and a successful one
 * moves it to the confirmation, which replaces the button.
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
  const captchaBox = useRef<HTMLDivElement>(null);
  const captcha = useWafCaptcha(captchaBox);
  const captchaPending = captcha.configured && captcha.token === null;
  const outcome = useRef<HTMLParagraphElement>(null);

  // The confirmation replaces the Submit button, which held focus.
  useEffect(() => {
    if (status === "success") outcome.current?.focus();
  }, [status]);

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
    // A control inside the puzzle may submit the form; that is not the visitor's submit.
    const submitter = (event.nativeEvent as SubmitEvent).submitter;
    if (submitter != null && captchaBox.current?.contains(submitter)) return;
    setAttempted(true);
    if (!canSubmit) {
      // Field-level errors are enough — no duplicate form summary. Focus goes
      // to the first field with one; its description is the error.
      setMessage(null);
      const firstInvalid =
        emailOver || emailMissing || emailInvalid
          ? "waitlist-email"
          : nameOver || nameMissing
            ? "waitlist-name"
            : orgOver
              ? "waitlist-org"
              : "waitlist-role";
      document.getElementById(firstInvalid)?.focus();
      return;
    }
    if (captchaPending) {
      // When the puzzle did not load, its own message is already on the page.
      if (!captcha.unavailable) {
        setStatus("error");
        setMessage("Solve the puzzle to continue");
      }
      return;
    }
    setStatus("submitting");
    setMessage(null);
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (captcha.token !== null) headers["x-aws-waf-token"] = captcha.token;
    try {
      const response = await fetch(`${apiBaseUrl()}/api/v1/waitlist`, {
        method: "POST",
        headers,
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
      // The firewall refused the token (expired): a 405 alone is the generic error.
      if (response.headers.get("x-amzn-waf-action") === "captcha") {
        setStatus("error");
        setMessage("Please solve the puzzle again");
        captcha.reset();
        return;
      }
      const body = (await response.json().catch(() => null)) as {
        error?: { code?: string; message?: string };
      } | null;
      setStatus("error");
      setMessage(body?.error?.message ?? "Something went wrong. Please try again.");
    } catch {
      setStatus("error");
      setMessage("Something went wrong. Please try again.");
    }
  };

  const done = status === "success";
  const disabled = done || status === "submitting";

  const emailOverMsg = overLimitMessage(email.length, WAITLIST_LIMITS.email);
  const nameOverMsg = overLimitMessage(name.length, WAITLIST_LIMITS.name);
  const orgOverMsg = overLimitMessage(organisation.length, WAITLIST_LIMITS.organisation);
  const roleOverMsg = overLimitMessage(roleOrReason.length, WAITLIST_LIMITS.roleOrReason);

  return (
    <form
      onSubmit={onSubmit}
      onFocus={captcha.arm}
      className="flex w-full flex-col gap-5"
      noValidate
    >
      <Field
        id="waitlist-email"
        counting={emailOverMsg !== null}
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
        counting={nameOverMsg !== null}
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
        counting={orgOverMsg !== null}
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
        counting={roleOverMsg !== null}
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

      {/* The firewall's puzzle, drawn by AWS. Empty until the first focus, when the
          negative margin cancels its flex gap so the form keeps its rhythm. */}
      {captcha.configured && !done && (
        <div ref={captchaBox} data-testid="waf-captcha" className="empty:-mt-5" />
      )}
      {captcha.unavailable && (
        <p role="status" className={cn(SPLASH_PROSE, "text-red")}>
          The sign-up check did not load. Reload the page to try again.
        </p>
      )}

      {message !== null && (
        <p
          ref={outcome}
          tabIndex={-1}
          role={status === "error" ? "alert" : "status"}
          className={cn(SPLASH_PROSE, "outline-hidden", status === "error" ? "text-red" : "text-navy")}
        >
          {message}
        </p>
      )}
      {!done && (
        <div>
          <Button
            type="submit"
            disabled={status === "submitting"}
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
    `mt-1.5 w-full border bg-paper px-3 py-2.5 ${SPLASH_PROSE} text-navy`,
    invalid ? "border-red" : "border-navy",
  );
}

function Field({
  id,
  label,
  labelExtra,
  error,
  counting,
  children,
}: {
  id: string;
  label: string;
  labelExtra?: ReactNode;
  error: string | null;
  /** The error is the over-limit count, which changes with each key press:
   *  it is the field's description, not an alert spoken on every key. */
  counting: boolean;
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
        <p id={errorId} role={counting ? undefined : "alert"} className={`mt-1.5 ${SPLASH_PROSE} text-red`}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
