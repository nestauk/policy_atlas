/*
 * The one date formatter (task 058, consolidation batch B). Every place that
 * shows a date names one of three forms:
 *
 *   short  "5 Nov" within the current year, "12 Oct 2025" otherwise (the lists)
 *   long   "6 November 2026" (the report's date line)
 *   time   "09:02" (History's rows)
 *
 * One fixed form for every reader rather than the browser's locale
 * ("11/5/2026" and "05/11/2026" are different days to two colleagues), and
 * never relative ("2 days ago" goes stale under an open tab and in a pasted
 * screenshot; lead ruling P7, round 10). The month and day names are fixed
 * here, so no locale can turn "Sep" into "Sept". Times are the reader's
 * local time, on the 24-hour clock.
 */

/** The three forms a date takes on screen. */
export type DateForm = "short" | "long" | "time";

const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/**
 * A date in one of its three forms.
 *
 * Args:
 *   value: An ISO 8601 timestamp, or a `Date`.
 *   form: `short` ("5 Nov", "12 Oct 2025"), `long` ("6 November 2026") or
 *     `time` ("09:02").
 *   options: `now`, the current time for the short form's year comparison
 *     (a parameter so tests need no clock); `weekday`, the long form led by
 *     its day ("Tuesday 3 November 2026", History's day headings).
 *
 * Returns:
 *   The date in the reader's local time zone, or "" for an unreadable value.
 */
export function formatDate(
  value: string | Date,
  form: DateForm,
  options: { now?: Date; weekday?: boolean } = {},
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "";
  if (form === "time") {
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
  if (form === "long") {
    const day = `${date.getDate()} ${MONTHS_LONG[date.getMonth()]} ${date.getFullYear()}`;
    return options.weekday === true ? `${WEEKDAYS[date.getDay()]} ${day}` : day;
  }
  const now = options.now ?? new Date();
  const dayMonth = `${date.getDate()} ${MONTHS_SHORT[date.getMonth()]}`;
  return date.getFullYear() === now.getFullYear() ? dayMonth : `${dayMonth} ${date.getFullYear()}`;
}
