import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { formatDate } from "../../lib/dates";
import { formatCount } from "../../lib/format";
import { rememberedKey } from "../../lib/remembered";
import { Button } from "../../ui/brand/Button";
import { FilterChip } from "../../ui/brand/Chip";
import { cn } from "../../ui/brand/cn";
import { QUIET_CONTROL_CLASS } from "../../ui/brand/inlineActions";
import { PANE_LABEL_CLASS } from "../../ui/brand/label";
import { PageBackLink } from "../../ui/brand/PageHeader";
import { ChoiceRow } from "../../views/workspace/PartCard";
import {
  OpsApiError,
  useCohorts,
  useOrganisations,
  usePeople,
  useRecipientPreview,
  useSendAnnouncement,
  useSendTest,
  useUploadImage,
  type AnnouncementKind,
  type Audience,
  type RecipientPreview,
} from "../api";
import { plural, sentence } from "../format";
import { Dialog, FailedDialog, FailedLine, Field, FormHeader, INPUT_CLASS, SearchSelect } from "../ui";
import { EmailPreview, KIND_WORDS, LEFT_OUT_WORDS, Marked, leftOutReasons, leftOutTotal } from "./announcementParts";

/* Compose (design annex § Compose and § Confirm dialog). */

/** The fields the browser keeps until the email is sent (not the picture's bytes). */
interface Draft {
  kind: AnnouncementKind;
  everyone: boolean;
  chosen: string[];
  subject: string;
  body: string;
  button_label: string;
  button_url: string;
  image_url: string;
  image_alt: string;
}

const EMPTY: Draft = {
  kind: "product_update",
  everyone: false,
  chosen: [],
  subject: "",
  body: "",
  button_label: "",
  button_url: "",
  image_url: "",
  image_alt: "",
};

const DRAFT_KEY = rememberedKey("ops-announcement", "new");

function readDraft(): Draft {
  try {
    const stored = window.localStorage.getItem(DRAFT_KEY);
    return stored === null ? EMPTY : { ...EMPTY, ...(JSON.parse(stored) as Partial<Draft>) };
  } catch {
    return EMPTY;
  }
}

function writeDraft(draft: Draft | null) {
  try {
    if (draft === null) window.localStorage.removeItem(DRAFT_KEY);
    else window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // Without storage a reload loses the text; the page works the same.
  }
}

/** The audience as the routes take it. A chosen item is "cohort:<id>", "org:<id>" or "user:<id>". */
function audienceOf(draft: Draft): Audience {
  const ids = (prefix: string) => draft.chosen.filter((key) => key.startsWith(prefix)).map((key) => key.slice(prefix.length));
  return draft.everyone
    ? { everyone: true, cohort_ids: [], org_ids: [], user_ids: [] }
    : { everyone: false, cohort_ids: ids("cohort:"), org_ids: ids("org:"), user_ids: ids("user:") };
}

/** The message fields as the routes take them: an empty optional field is null. */
function messageOf(draft: Draft) {
  const optional = (value: string) => (value.trim() === "" ? null : value.trim());
  return {
    subject: draft.subject,
    body: draft.body,
    button_label: optional(draft.button_label),
    button_url: optional(draft.button_url),
    image_url: optional(draft.image_url),
    image_alt: optional(draft.image_alt),
  };
}

const FIELDS = ["subject", "body", "button_label", "button_url", "image_url", "image_alt"] as const;
type FieldName = (typeof FIELDS)[number] | "form";

/** The field a 422 `invalid_message` names in its details; any other answer sits under the test button. */
function fieldOf(details: unknown): FieldName {
  const field = (details as { field?: unknown } | null)?.field;
  return FIELDS.find((name) => name === field) ?? "form";
}

/** The picture at most 1200 pixels wide, PNG kept as PNG and JPEG as JPEG. */
async function shrink(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  if (bitmap.width <= 1200) {
    bitmap.close();
    return file;
  }
  const canvas = document.createElement("canvas");
  canvas.width = 1200;
  canvas.height = Math.round((bitmap.height * 1200) / bitmap.width);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob === null ? reject(new Error("no picture")) : resolve(blob)), file.type, 0.9),
  );
}

function base64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).replace(/^data:[^,]*,/, ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

const KINDS: ReadonlyArray<{ kind: AnnouncementKind; label: string; sentence: string }> = [
  {
    kind: "product_update",
    label: "Product update",
    sentence:
      "New features and news. The email has an unsubscribe link. People who unsubscribed or have not signed in yet do not get it.",
  },
  {
    kind: "service_notice",
    label: "Service notice",
    sentence: "Things people must know to use their account: downtime, security, changes to terms. No unsubscribe link.",
  },
];

const ADD_LABEL = "Add a cohort, an organisation or a person";
const SECTION_CLASS = "flex flex-col gap-5 border border-line-2 bg-paper p-6 shadow-paper max-md:p-4";

export function ComposeAnnouncementView() {
  const navigate = useNavigate();
  const cohorts = useCohorts();
  const organisations = useOrganisations();
  const people = usePeople();
  const previewCall = useRecipientPreview();
  const sendTest = useSendTest();
  const upload = useUploadImage();
  const send = useSendAnnouncement();
  const testHelpId = useId();
  const fileRef = useRef<HTMLInputElement>(null);

  const [draft, setDraft] = useState<Draft>(readDraft);
  const update = (change: Partial<Draft>) => setDraft((current) => ({ ...current, ...change }));
  useEffect(() => writeDraft(draft), [draft]);

  // The server's answer for the kind and audience it was asked about.
  const [preview, setPreview] = useState<{ key: string; answer: RecipientPreview } | null>(null);
  // The kind and audience whose answer failed, until it is asked again.
  const [failedKey, setFailedKey] = useState<string | null>(null);
  const [previewRun, setPreviewRun] = useState(0);
  const latest = useRef(0);
  const audience = audienceOf(draft);
  const audienceKey = JSON.stringify([draft.kind, audience]);
  const noAudience = !draft.everyone && draft.chosen.length === 0;
  const askPreview = previewCall.mutateAsync;
  useEffect(() => {
    // Asked again 400 ms after the last change; an older answer is dropped.
    const mine = ++latest.current;
    if (noAudience) return;
    const [kind, asked] = JSON.parse(audienceKey) as [AnnouncementKind, Audience];
    const timer = window.setTimeout(() => {
      askPreview({ kind, audience: asked })
        .then((answer) => {
          if (mine !== latest.current) return;
          setFailedKey(null);
          setPreview({ key: audienceKey, answer });
        })
        .catch(() => {
          if (mine === latest.current) setFailedKey(audienceKey);
        });
    }, 400);
    return () => window.clearTimeout(timer);
  }, [askPreview, audienceKey, noAudience, previewRun]);
  const previewFailed = !noAudience && failedKey === audienceKey;
  const answer = !noAudience && preview !== null ? preview.answer : null;
  const fresh = answer !== null && preview?.key === audienceKey;

  // The test of the current text: the fields and the kind when the last test succeeded.
  const message = messageOf(draft);
  const textKey = JSON.stringify([draft.kind, message]);
  const [tested, setTested] = useState<{ key: string; at: Date } | null>(null);
  const testedNow = tested !== null && tested.key === textKey;
  const [fieldError, setFieldError] = useState<{ field: FieldName; text: string } | null>(null);
  const [testFailed, setTestFailed] = useState<string | null>(null);
  const errorFor = (field: FieldName) => (fieldError?.field === field ? fieldError.text : null);
  // The picture's description sits under its own field while a picture is in;
  // its address, or a description with no picture, sits under the picture.
  const altError = draft.image_url === "" ? null : errorFor("image_alt");
  const pictureLineError = errorFor("image_url") ?? (draft.image_url === "" ? errorFor("image_alt") : null);

  const runTest = () => {
    setFieldError(null);
    setTestFailed(null);
    const key = textKey;
    sendTest.mutate(
      { ...message, kind: draft.kind },
      {
        onSuccess: () => setTested({ key, at: new Date() }),
        onError: (error) => {
          if (error instanceof OpsApiError && error.status === 422 && error.message !== "") {
            setFieldError({ field: fieldOf(error.details), text: sentence(error.message) });
          } else if (error instanceof OpsApiError && error.status === 409 && error.message !== "") {
            setTestFailed(sentence(error.message));
          } else {
            setTestFailed("The test email was not sent.");
          }
        },
      },
    );
  };

  // The picture: the browser's own copy for the preview, the stored address for the email.
  const [pictureSrc, setPictureSrc] = useState<string | null>(null);
  const [pictureError, setPictureError] = useState<string | null>(null);
  useEffect(() => () => {
    if (pictureSrc !== null) URL.revokeObjectURL(pictureSrc);
  }, [pictureSrc]);
  const choosePicture = async (file: File | undefined) => {
    if (file === undefined) return;
    setPictureError(null);
    if (file.type !== "image/png" && file.type !== "image/jpeg") {
      setPictureError("Choose a PNG or JPEG picture.");
      return;
    }
    try {
      const blob = await shrink(file);
      const { url } = await upload.mutateAsync({ content_type: file.type, data_base64: await base64(blob) });
      setPictureSrc(URL.createObjectURL(blob));
      update({ image_url: url });
    } catch (error) {
      setPictureError(
        error instanceof OpsApiError && error.status === 422 && error.message !== ""
          ? sentence(error.message)
          : "Could not add the picture. Try again.",
      );
    }
  };
  const removePicture = () => {
    setPictureSrc(null);
    update({ image_url: "", image_alt: "" });
  };

  const [confirming, setConfirming] = useState(false);
  const [listOpen, setListOpen] = useState(false);

  // The audience search over the lists the ops pages already read.
  const names = new Map<string, string>([
    ...(cohorts.data ?? []).map((cohort) => [`cohort:${cohort.cohort_id}`, `Cohort: ${cohort.name}`] as const),
    ...(organisations.data ?? []).map((org) => [`org:${org.org_id}`, `Organisation: ${org.name}`] as const),
    ...(people.data ?? []).map((person) => [`user:${person.user_id}`, `Person: ${person.display_name}`] as const),
  ]);
  const searchable = (people.data ?? []).reduce(
    (labels, person) => labels.set(`user:${person.user_id}`, `Person: ${person.display_name}${person.email ? `, ${person.email}` : ""}`),
    new Map(names),
  );
  const options = [...searchable]
    .filter(([key]) => !draft.chosen.includes(key))
    .map(([value, label]) => ({ value, label }));
  const chosenWords = draft.chosen.map((key) => (names.get(key) ?? "").replace(/^[^:]+: /, ""));

  const blockedByTest = !testedNow;
  const canSend = testedNow && fresh && answer.will_get > 0 && !noAudience;

  return (
    <>
      <FormHeader back={<PageBackLink to="/announcements">Announcements</PageBackLink>} title="New announcement" />
      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="flex min-w-0 flex-col gap-6">
          <section aria-labelledby="ann-kind" className={SECTION_CLASS}>
            <h2 id="ann-kind" className={PANE_LABEL_CLASS}>
              1 · Kind
            </h2>
            <div role="radiogroup" aria-labelledby="ann-kind" className="flex flex-col gap-1">
              {KINDS.map((choice) => (
                <ChoiceRow
                  key={choice.kind}
                  label={choice.label}
                  sentences={[choice.sentence]}
                  selected={draft.kind === choice.kind}
                  disabled={false}
                  onChoose={() => update({ kind: choice.kind })}
                />
              ))}
            </div>
          </section>

          <section aria-labelledby="ann-who" className={SECTION_CLASS}>
            <h2 id="ann-who" className={PANE_LABEL_CLASS}>
              2 · Who gets it
            </h2>
            <div role="radiogroup" aria-labelledby="ann-who" className="flex flex-col gap-1">
              <ChoiceRow
                label="Everyone with an account"
                sentences={[]}
                selected={draft.everyone}
                disabled={false}
                onChoose={() => update({ everyone: true })}
              />
              <ChoiceRow
                label="Chosen cohorts, organisations and people"
                sentences={[]}
                selected={!draft.everyone}
                disabled={false}
                onChoose={() => update({ everyone: false })}
              />
            </div>
            {!draft.everyone && (
              <div className="flex flex-col gap-3">
                {draft.chosen.length > 0 && (
                  <ul aria-label="Chosen" className="flex flex-wrap gap-2">
                    {draft.chosen.map((key, index) => (
                      <li key={key} className="max-w-full">
                        <FilterChip
                          applied
                          staticWords
                          onClear={() => update({ chosen: draft.chosen.filter((other) => other !== key) })}
                          clearLabel={`Remove ${chosenWords[index]}`}
                        >
                          {names.get(key) ?? ""}
                        </FilterChip>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="max-w-md">
                  <SearchSelect
                    label={ADD_LABEL}
                    options={options}
                    value=""
                    onChange={(key) => update({ chosen: [...draft.chosen, key] })}
                    placeholder={ADD_LABEL}
                    filterLabel={ADD_LABEL}
                    empty="No cohort, organisation or person matches."
                  />
                </div>
              </div>
            )}
            {previewFailed ? (
              <FailedLine message="Could not work out who gets this email." onRetry={() => setPreviewRun((n) => n + 1)} />
            ) : (
              answer !== null && (
                <div aria-live="polite" className="border-t border-line pt-4">
                  <p className="text-body text-navy">
                    <b className="font-bold tabular-nums">{formatCount(answer.will_get)}</b> people get this email
                  </p>
                  <p className="mt-1 text-body text-grey">
                    {`${formatCount(answer.chosen)} chosen.`}
                    {leftOutTotal(answer) > 0 && ` ${formatCount(leftOutTotal(answer))} left out: ${leftOutReasons(answer)}.`}{" "}
                    A person in two groups gets one email.{" "}
                    <button type="button" onClick={() => setListOpen(true)} className={cn(QUIET_CONTROL_CLASS, "text-body")}>
                      See the list
                    </button>
                  </p>
                </div>
              )
            )}
          </section>

          <section aria-labelledby="ann-message" className={SECTION_CLASS}>
            <h2 id="ann-message" className={PANE_LABEL_CLASS}>
              3 · Message
            </h2>
            <Field id="ann-subject" label="Subject" error={errorFor("subject")}>
              {(describedBy) => (
                <input
                  id="ann-subject"
                  maxLength={150}
                  autoComplete="off"
                  value={draft.subject}
                  aria-invalid={errorFor("subject") !== null}
                  aria-describedby={describedBy}
                  onChange={(event) => update({ subject: event.target.value })}
                  className={INPUT_CLASS}
                />
              )}
            </Field>
            <Field
              id="ann-body"
              label="Message"
              help='Plain text. Leave an empty line between paragraphs. Start a line with "- " to make a list.'
              error={errorFor("body")}
            >
              {(describedBy) => (
                <textarea
                  id="ann-body"
                  rows={9}
                  maxLength={10000}
                  value={draft.body}
                  aria-invalid={errorFor("body") !== null}
                  aria-describedby={describedBy}
                  onChange={(event) => update({ body: event.target.value })}
                  className={cn(INPUT_CLASS, "h-auto resize-y py-2 leading-[1.55]")}
                />
              )}
            </Field>
            <div className="flex flex-col gap-1.5">
              <p id="ann-picture" className="text-body font-semibold text-navy">
                Picture (optional)
              </p>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg"
                aria-labelledby="ann-picture"
                className="sr-only"
                tabIndex={-1}
                onChange={(event) => {
                  void choosePicture(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
              {draft.image_url === "" ? (
                <div>
                  <Button variant="outline" disabled={upload.isPending} onClick={() => fileRef.current?.click()}>
                    Add a picture
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap items-start gap-4">
                  {pictureSrc !== null && (
                    <img src={pictureSrc} alt="" className="h-20 w-32 shrink-0 border border-line-2 object-cover" />
                  )}
                  <div className="min-w-0 flex-[1_1_16rem]">
                    <Field
                      id="ann-picture-alt"
                      label="Describe the picture"
                      help="People see these words when their mail program hides pictures."
                      error={altError}
                    >
                      {(describedBy) => (
                        <input
                          id="ann-picture-alt"
                          required
                          maxLength={200}
                          autoComplete="off"
                          value={draft.image_alt}
                          aria-invalid={altError !== null}
                          aria-describedby={describedBy}
                          onChange={(event) => update({ image_alt: event.target.value })}
                          className={INPUT_CLASS}
                        />
                      )}
                    </Field>
                    <button type="button" onClick={removePicture} className={cn(QUIET_CONTROL_CLASS, "mt-2 text-body")}>
                      Remove
                    </button>
                  </div>
                </div>
              )}
              {pictureError !== null && (
                <p role="alert" className="text-body text-red">
                  {pictureError}
                </p>
              )}
              {pictureLineError !== null && <p className="text-body text-red">{pictureLineError}</p>}
              <p className="text-body text-yellow-deep">Anyone with the link can open this picture. Do not show private data.</p>
            </div>
            <div className="grid gap-5 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
              <Field id="ann-button-label" label="Button text (optional)" error={errorFor("button_label")}>
                {(describedBy) => (
                  <input
                    id="ann-button-label"
                    maxLength={40}
                    autoComplete="off"
                    value={draft.button_label}
                    aria-invalid={errorFor("button_label") !== null}
                    aria-describedby={describedBy}
                    onChange={(event) => update({ button_label: event.target.value })}
                    className={INPUT_CLASS}
                  />
                )}
              </Field>
              <Field id="ann-button-url" label="Button link" error={errorFor("button_url")}>
                {(describedBy) => (
                  <input
                    id="ann-button-url"
                    type="url"
                    autoComplete="off"
                    spellCheck={false}
                    value={draft.button_url}
                    aria-invalid={errorFor("button_url") !== null}
                    aria-describedby={describedBy}
                    onChange={(event) => update({ button_url: event.target.value })}
                    className={INPUT_CLASS}
                  />
                )}
              </Field>
            </div>
          </section>
        </div>

        <aside className="flex min-w-0 flex-col gap-6 lg:sticky lg:top-6">
          <section aria-labelledby="ann-preview" className={SECTION_CLASS}>
            <div className="flex flex-col gap-1">
              <h2 id="ann-preview" className={PANE_LABEL_CLASS}>
                Preview
              </h2>
              <p className="text-meta text-grey">From: Policy Atlas &lt;updates@…&gt;</p>
            </div>
            <EmailPreview
              kind={draft.kind}
              subject={draft.subject}
              body={draft.body}
              buttonLabel={message.button_label}
              picture={draft.image_url === "" ? null : { src: pictureSrc, alt: draft.image_alt }}
            />
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" disabled={sendTest.isPending} onClick={runTest}>
                Send a test to me
              </Button>
              {testedNow && (
                <span role="status" className="text-meta text-green-deep">
                  <Marked colour="green">{`Test sent to you at ${formatDate(tested.at, "time")}`}</Marked>
                </span>
              )}
            </div>
            {errorFor("form") !== null && (
              <p role="alert" className="text-body text-red">
                {errorFor("form")}
              </p>
            )}
          </section>
          <div className="flex flex-col items-end gap-2">
            <Button
              size="entry"
              disabled={!canSend}
              aria-describedby={blockedByTest ? testHelpId : undefined}
              onClick={() => setConfirming(true)}
            >
              Check and send
            </Button>
            {blockedByTest && (
              <p id={testHelpId} className="text-right text-body text-grey">
                You must send yourself a test before you can send.
              </p>
            )}
          </div>
        </aside>
      </div>

      {listOpen && answer !== null && (
        <Dialog
          open
          onOpenChange={setListOpen}
          title={`${plural(answer.will_get, "person", "people")} get this email`}
          footer={
            <Button variant="ghost" onClick={() => setListOpen(false)}>
              Close
            </Button>
          }
        >
          <ul className="border-y border-line">
            {answer.recipients.map((person) => (
              <li key={person.user_id} className="flex flex-wrap gap-x-3 border-t border-line py-2 text-meta first:border-t-0">
                <span className="font-semibold text-navy">{person.name}</span>
                {person.email !== null && <span className="text-grey">{person.email}</span>}
                {person.reason !== null && (
                  <span className="text-grey">{`Left out: ${LEFT_OUT_WORDS[person.reason] ?? person.reason}`}</span>
                )}
              </li>
            ))}
          </ul>
        </Dialog>
      )}

      {testFailed !== null && (
        <FailedDialog
          message={testFailed}
          description="Nothing was sent. Check the message and try again."
          onRetry={runTest}
          onClose={() => setTestFailed(null)}
        />
      )}

      {confirming && answer !== null && (
        <ConfirmDialog
          answer={answer}
          subject={draft.subject}
          kind={draft.kind}
          who={draft.everyone ? "Everyone with an account" : chosenWords.join(", ")}
          pending={send.isPending}
          error={send.error}
          onClose={() => {
            send.reset();
            setConfirming(false);
          }}
          onSend={(fingerprint) =>
            send.mutate(
              { ...message, kind: draft.kind, audience, fingerprint },
              {
                onSuccess: ({ announcement_id }) => {
                  writeDraft(null);
                  navigate(`/announcements/${announcement_id}`);
                },
                onError: (error) => {
                  if (error instanceof OpsApiError && error.code === "recipients_changed") {
                    setPreview({ key: audienceKey, answer: error.details as RecipientPreview });
                  }
                },
              },
            )
          }
        />
      )}
    </>
  );
}

/**
 * The confirm dialog: what goes to whom, the warning, and the number typed
 * back. When the server finds the list changed, it shows the new numbers and
 * asks for the new number.
 */
function ConfirmDialog({
  answer,
  subject,
  kind,
  who,
  pending,
  error,
  onClose,
  onSend,
}: {
  answer: RecipientPreview;
  subject: string;
  kind: AnnouncementKind;
  who: string;
  pending: boolean;
  error: Error | null;
  onClose: () => void;
  onSend: (fingerprint: string) => void;
}) {
  const [typed, setTyped] = useState("");
  const [shownFingerprint, setShownFingerprint] = useState(answer.fingerprint);
  const changed = error instanceof OpsApiError && error.code === "recipients_changed";
  // The list changed: the number typed for the old list no longer counts.
  if (answer.fingerprint !== shownFingerprint) {
    setShownFingerprint(answer.fingerprint);
    setTyped("");
  }
  const n = answer.will_get;
  const matches = typed.replace(/[\s,]/g, "") === String(n);
  const left = leftOutTotal(answer);
  const failure =
    error === null || changed
      ? null
      : error instanceof OpsApiError && (error.status === 422 || error.status === 409) && error.message !== ""
        ? sentence(error.message)
        : "The email was not sent. Try again.";

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={`Send this email to ${plural(n, "person", "people")}?`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Go back
          </Button>
          <Button disabled={!matches || pending} onClick={() => onSend(answer.fingerprint)}>
            {`Send to ${plural(n, "person", "people")}`}
          </Button>
        </>
      }
    >
      {changed && (
        <p role="alert" className="mb-4 border border-yellow-tint-edge bg-yellow-tint px-3.5 py-3 text-body text-yellow-deep">
          {`The list changed: it is now ${plural(n, "person", "people")}. Check it and confirm again.`}
        </p>
      )}
      <dl className="flex flex-col gap-3.5">
        {[
          ["Subject", subject],
          ["Kind", KIND_WORDS[kind]],
          ["Who gets it", who],
          ["Left out", left === 0 ? "No one" : `${plural(left, "person", "people")}: ${leftOutReasons(answer)}.`],
        ].map(([term, value]) => (
          <div key={term}>
            <dt className="text-caption font-bold uppercase tracking-label text-grey">{term}</dt>
            <dd className="text-body text-ink [overflow-wrap:anywhere]">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-5 border border-yellow-tint-edge bg-yellow-tint px-3.5 py-3 text-body text-yellow-deep">
        You cannot take an email back after you send it.
      </p>
      <div className="mt-5 max-w-40">
        <Field id="ann-confirm" label={`Type ${formatCount(n)} to confirm`}>
          <input
            id="ann-confirm"
            inputMode="numeric"
            autoComplete="off"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            className={cn(INPUT_CLASS, "tabular-nums")}
          />
        </Field>
      </div>
      {failure !== null && (
        <p role="alert" className="mt-3 text-body text-red">
          {failure}
        </p>
      )}
    </Dialog>
  );
}
