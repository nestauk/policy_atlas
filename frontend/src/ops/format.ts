import { formatDate } from "../lib/dates";
import { formatCount } from "../lib/format";

const HOUR_MS = 60 * 60 * 1000;

/**
 * How long ago, in the ops pages' short form ("4 min ago", "2 h ago",
 * "3 d ago"; the short date after a month). The ops script asks for relative
 * times in the People and Requests tables, where the product never uses them.
 */
export function ago(iso: string, now = Date.now()): string {
  const minutes = Math.max(1, Math.floor((now - Date.parse(iso)) / 60000));
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} d ago`;
  return formatDate(iso, "short");
}

/** Whether an invitation went out less than an hour ago (the resend cooldown). */
export function inCooldown(invitedAt: string | null | undefined, now = Date.now()): boolean {
  return invitedAt != null && now - Date.parse(invitedAt) < HOUR_MS;
}

/** The disabled resend's hint: "sent 2 h ago, try again after 15:40". */
export function resendHint(invitedAt: string, now = Date.now()): string {
  const after = new Date(Date.parse(invitedAt) + HOUR_MS);
  return `sent ${ago(invitedAt, now)}, try again after ${formatDate(after, "time")}`;
}

/**
 * A line of facts joined with " · " (DESIGN.md, the Middot Rule): each dot
 * binds to the field before it with a no-break space, so a wrapped line
 * never starts with a dot.
 */
export function facts(...parts: string[]): string {
  return parts.join(" · ");
}

/** A limit's value: the count, or "no limit" for none (null, or an override of 0). */
export function limitWord(value: number | null | undefined): string {
  return value == null || value === 0 ? "no limit" : formatCount(value);
}

/** "1 task", "2 tasks". */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`;
}

/** A command's refusal as a sentence: first letter up, a full stop at the end. */
export function sentence(message: string): string {
  const text = message.charAt(0).toUpperCase() + message.slice(1);
  return /[.!?]$/.test(text) ? text : `${text}.`;
}

/**
 * The organisation an `enrolled_elsewhere` refusal names. The error envelope
 * carries only the command's sentence ("a@b is already in Nesta. Nothing was
 * written. ..."), so the name is read from it.
 */
export function orgInRefusal(message: string): string | null {
  return /is already in (.+?)\. Nothing was written/.exec(message)?.[1] ?? null;
}
