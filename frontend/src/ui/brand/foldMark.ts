/**
 * Fold-mark geometry: one square sheet whose corners fold to the centre.
 *
 * Ported from the splash-page / synthesis-report design prototypes so the
 * product logo matches the design-site mark.
 */

export type Corner = "TL" | "TR" | "BR" | "BL";
export type Point = readonly [number, number];

export interface FoldPath {
  d: string;
  fill: string;
}

/** Half-size of the unrotated square in the logo viewBox. */
export const H = 75;

export const MID: readonly Point[] = [
  [-H, 0],
  [0, -H],
  [H, 0],
  [0, H],
];

export const CORNERS: readonly Corner[] = ["TL", "TR", "BR", "BL"];

export const OUTER: Record<Corner, Point> = {
  TL: [-H, -H],
  TR: [H, -H],
  BR: [H, H],
  BL: [-H, H],
};

export const ALL: readonly Corner[] = ["TL", "TR", "BR", "BL"];

/** CSS size of the header / nav mark — same box for animated and static. */
export const BRAND_MARK_SIZE = 17;

/**
 * Shared viewBox so the diamond reads the same size whether it is
 * rotating (needs headroom) or the static shut frame.
 * 10-unit padding each side; diamond vertices sit at ±75.
 */
export const BRAND_MARK_VIEWBOX = "-85 -85 170 170";

/** App hero blue (`--color-blue`); prototype used `#0000F5`. */
export const BLUE = "#0000ff";
export const SAND = "#ECC77F";
export const TEAL = "#6FBFA7";
export const SALMON = "#F09B80";
export const PINK = "#E8B9C8";

/** One animation keyframe: folded corners, base rotation degrees, sheet colour. */
export type FoldFrame = readonly [readonly Corner[], number, string];

/**
 * Thirty-six frames. Index 4 is the static product logo ("frame 5" in the
 * design strip): all corners folded, 0°, solid blue diamond.
 */
export const FRAMES: readonly FoldFrame[] = [
  [[], 0, SAND],
  [["TL"], 0, SAND],
  [["TL", "TR"], 0, SAND],
  [["TL", "TR", "BL"], 0, SAND],
  [ALL, 0, BLUE],
  [ALL, 45, BLUE],
  [["TL", "BR", "BL"], 45, TEAL],
  [["BL", "BR"], 45, TEAL],
  [["BR"], 45, TEAL],
  [[], 45, TEAL],
  [["TR"], 45, TEAL],
  [["TL", "TR"], 45, TEAL],
  [["TL", "TR", "BR"], 45, TEAL],
  [ALL, 45, BLUE],
  [ALL, 0, BLUE],
  [["TL", "TR", "BR"], 0, SALMON],
  [["TR", "BR"], 0, SALMON],
  [["BR"], 0, SALMON],
  [[], 0, SALMON],
  [["TL"], 0, SALMON],
  [["TL", "BL"], 0, SALMON],
  [["TL", "TR", "BL"], 0, SALMON],
  [ALL, 0, BLUE],
  [ALL, 45, BLUE],
  [["TL", "BR", "BL"], 45, PINK],
  [["BL", "BR"], 45, PINK],
  [["BR"], 45, PINK],
  [[], 45, PINK],
  [["TR"], 45, PINK],
  [["TL", "TR"], 45, PINK],
  [["TL", "TR", "BR"], 45, PINK],
  [ALL, 45, BLUE],
  [ALL, 0, BLUE],
  [["TL", "TR", "BR"], 0, SAND],
  [["TR", "BR"], 0, SAND],
  [["BR"], 0, SAND],
];

/** Static logo frame — prototype "frame 5" (1-based), index 4. */
export const STATIC_LOGO_FRAME = 4;

const FPS = 5.6;
const ROTATE_MS = 714;

function has(set: readonly Corner[], c: Corner): boolean {
  return set.indexOf(c) > -1;
}

function prune(pts: Point[]): Point[] {
  return pts.filter((p, i) => {
    const a = pts[(i + pts.length - 1) % pts.length]!;
    const c = pts[(i + 1) % pts.length]!;
    return Math.abs((p[0] - a[0]) * (c[1] - p[1]) - (p[1] - a[1]) * (c[0] - p[0])) > 1e-9;
  });
}

function silhouette(folded: readonly Corner[]): Point[] {
  const pts: Point[] = [];
  CORNERS.forEach((c, i) => {
    pts.push(MID[i]!);
    if (!has(folded, c)) pts.push(OUTER[c]);
  });
  return prune(pts);
}

function flaps(folded: readonly Corner[]): Point[] | null {
  if (!folded.length) return null;
  if (folded.length === 4) return MID.slice();
  const idx = CORNERS.map((c, i) => (has(folded, c) ? i : -1)).filter((i) => i > -1);
  const start = idx.find((i) => idx.indexOf((i + 3) % 4) === -1);
  if (start === undefined) return null;
  const out: Point[] = [[0, 0]];
  for (let k = 0; k <= folded.length; k++) out.push(MID[(start + k) % 4]!);
  return out;
}

function toPath(pts: readonly Point[], deg: number): string {
  const r = (deg * Math.PI) / 180;
  const cs = Math.cos(r);
  const sn = Math.sin(r);
  const p = pts.map(([x, y]) =>
    [x * cs - y * sn, x * sn + y * cs].map((n) => Math.round(n * 100) / 100),
  );
  return `M${p[0]!.join(" ")}${p
    .slice(1)
    .map((q) => `L${q.join(" ")}`)
    .join("")}Z`;
}

/**
 * Paths for one frame index, optionally with an explicit rotation.
 *
 * @param n - Frame index into {@link FRAMES}.
 * @param deg - Override rotation; defaults to the frame's base degrees.
 * @param reverse - Colour of the sheet's folded reverse (blue on light
 *   surfaces, white on dark ones).
 * @returns SVG path descriptors to paint.
 */
export function framePaths(n: number, deg?: number, reverse: string = BLUE): FoldPath[] {
  const [folded, baseDeg, colour] = FRAMES[n]!;
  const rot = deg === undefined ? baseDeg : deg;
  const out: FoldPath[] = [];
  if (folded.length < 4) {
    out.push({
      fill: colour === BLUE ? reverse : colour,
      d: toPath(silhouette(folded), rot),
    });
  }
  const f = flaps(folded);
  if (f) out.push({ fill: reverse, d: toPath(f, rot) });
  return out;
}

function shut(n: number, frames: readonly FoldFrame[] = FRAMES): boolean {
  return frames[n]![0].length === 4;
}

function isTurn(n: number, frames: readonly FoldFrame[] = FRAMES): boolean {
  return shut(n, frames) && shut((n + 1) % frames.length, frames);
}

function ease(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t);
}

/**
 * Paths at a wall-clock time in seconds (frame-rate independent playback).
 *
 * @param clock - Elapsed seconds into the loop.
 * @param reverse - Fold reverse colour.
 * @returns Paths for the interpolated frame at `clock`.
 */
export function pathsAt(clock: number, reverse: string = BLUE): FoldPath[] {
  const turnBeats = 1 + (ROTATE_MS / 1000) * FPS;
  const hold = 1 / turnBeats;
  const durs = FRAMES.map((_, k) => (isTurn(k) ? turnBeats : 1));
  const starts: number[] = [];
  let total = 0;
  durs.forEach((d) => {
    starts.push(total);
    total += d;
  });
  const p = (clock * FPS) % total;
  let n = FRAMES.length - 1;
  while (n > 0 && starts[n]! > p) n--;
  const t = (p - starts[n]!) / durs[n]!;
  let deg = FRAMES[n]![1];
  if (isTurn(n)) deg += 45 * ease(Math.max(0, (t - hold) / (1 - hold)));
  return framePaths(n, deg, reverse);
}

/** Pastel sheet palette used by the splash constellation. */
export const PASTEL_SHEET_COLOURS = [SAND, TEAL, SALMON, PINK] as const;

/**
 * Splash-field fold frames: same geometry as {@link FRAMES}, but shut frames
 * paint a solid colour and open frames cycle pastel sheets.
 *
 * @param sheetColours - Pastel palette for open/partially-folded frames.
 * @param shutColour - Colour for fully-shut diamond frames. White on dark
 *   backgrounds (splash); blue on light backgrounds (signed-in nav).
 * @returns A 36-frame sequence for the fold-mark animation.
 */
export function splashFoldFrames(
  sheetColours: readonly string[] = PASTEL_SHEET_COLOURS,
  shutColour = "#ffffff",
): FoldFrame[] {
  const [A, B, C, D] = sheetColours;
  const SHUT = shutColour;
  return [
    [["TL"], 0, A!],
    [["TL", "TR"], 0, A!],
    [["TL", "TR", "BL"], 0, A!],
    [ALL, 0, SHUT],
    [ALL, 45, SHUT],
    [["TL", "BR", "BL"], 45, B!],
    [["BL", "BR"], 45, B!],
    [["BR"], 45, B!],
    [[], 45, B!],
    [["TR"], 45, B!],
    [["TL", "TR"], 45, B!],
    [["TL", "TR", "BR"], 45, B!],
    [ALL, 45, SHUT],
    [ALL, 0, SHUT],
    [["TL", "TR", "BR"], 0, C!],
    [["TR", "BR"], 0, C!],
    [["BR"], 0, C!],
    [[], 0, C!],
    [["TL"], 0, C!],
    [["TL", "BL"], 0, C!],
    [["TL", "TR", "BL"], 0, C!],
    [ALL, 0, SHUT],
    [ALL, 45, SHUT],
    [["TL", "BR", "BL"], 45, D!],
    [["BL", "BR"], 45, D!],
    [["BR"], 45, D!],
    [[], 45, D!],
    [["TR"], 45, D!],
    [["TL", "TR"], 45, D!],
    [["TL", "TR", "BR"], 45, D!],
    [ALL, 45, SHUT],
    [ALL, 0, SHUT],
    [["TL", "TR", "BR"], 0, A!],
    [["TR", "BR"], 0, A!],
    [["BR"], 0, A!],
    [[], 0, A!],
  ];
}

export interface SplashPathsResult {
  paths: FoldPath[];
  frameIndex: number;
  degrees: number;
}

/**
 * Splash constellation paths at a clock position (rotation applied via SVG
 * transform, so path geometry stays at 0°).
 *
 * @param pos - Elapsed seconds into the loop (plus sheet offset).
 * @param frames - Frame table from {@link splashFoldFrames}.
 * @param flapColour - Colour of the folded-corner triangle on partial frames.
 *   Defaults to white (for dark backgrounds); pass blue for light backgrounds.
 * @returns Paths, frame index, and rotation degrees for the transform.
 */
export function splashPathsAt(
  pos: number,
  frames: readonly FoldFrame[] = splashFoldFrames(),
  flapColour = "#ffffff",
): SplashPathsResult {
  const turnBeats = 1 + (ROTATE_MS / 1000) * FPS;
  const hold = 1 / turnBeats;
  const durs = frames.map((_, k) => (isTurn(k, frames) ? turnBeats : 1));
  const starts: number[] = [];
  let total = 0;
  durs.forEach((du) => {
    starts.push(total);
    total += du;
  });
  const p = (((pos * FPS) % total) + total) % total;
  let n = frames.length - 1;
  while (n > 0 && starts[n]! > p) n--;
  const t = (p - starts[n]!) / durs[n]!;
  let deg = frames[n]![1];
  if (isTurn(n, frames)) deg += 45 * ease(Math.max(0, (t - hold) / (1 - hold)));
  const [folded, , colour] = frames[n]!;
  const out: FoldPath[] = [];
  if (folded.length < 4) out.push({ d: toPath(silhouette(folded), 0), fill: colour });
  const fl = flaps(folded);
  if (fl) out.push({ d: toPath(fl, 0), fill: folded.length === 4 ? colour : flapColour });
  return { paths: out, frameIndex: n, degrees: deg };
}

/** Hand-placed constellation seeds from the splash prototype. */
export const SPLASH_LAYOUT: readonly {
  x: string;
  y: string;
  size: number;
  opacity: number;
  off: number;
}[] = [
  { x: "78%", y: "17%", size: 250, opacity: 1, off: 0.0 },
  { x: "93%", y: "54%", size: 150, opacity: 0.5, off: 2.3 },
  { x: "69%", y: "80%", size: 310, opacity: 1, off: 4.7 },
  { x: "58%", y: "38%", size: 110, opacity: 0.3, off: 1.4 },
  { x: "30%", y: "11%", size: 66, opacity: 0.5, off: 3.6 },
  { x: "8%", y: "9%", size: 104, opacity: 1, off: 5.9 },
  { x: "20%", y: "89%", size: 158, opacity: 1, off: 7.1 },
  { x: "46%", y: "93%", size: 80, opacity: 0.3, off: 8.2 },
  { x: "88%", y: "90%", size: 72, opacity: 0.5, off: 6.4 },
  { x: "4%", y: "77%", size: 58, opacity: 0.3, off: 9.5 },
  { x: "62%", y: "4%", size: 96, opacity: 0.5, off: 11.2 },
  { x: "97%", y: "31%", size: 62, opacity: 0.3, off: 12.8 },
  { x: "83%", y: "68%", size: 54, opacity: 0.3, off: 10.4 },
  { x: "52%", y: "62%", size: 132, opacity: 0.5, off: 13.7 },
  { x: "35%", y: "99%", size: 190, opacity: 1, off: 15.1 },
  { x: "2%", y: "38%", size: 68, opacity: 0.3, off: 14.3 },
  { x: "15%", y: "58%", size: 46, opacity: 0.3, off: 16.6 },
  { x: "73%", y: "46%", size: 74, opacity: 0.5, off: 17.9 },
  { x: "44%", y: "20%", size: 52, opacity: 0.3, off: 18.4 },
  { x: "92%", y: "8%", size: 118, opacity: 1, off: 19.7 },
  { x: "26%", y: "31%", size: 44, opacity: 0.3, off: 20.6 },
  { x: "66%", y: "25%", size: 58, opacity: 0.5, off: 21.9 },
  { x: "38%", y: "52%", size: 88, opacity: 0.5, off: 23.2 },
  { x: "86%", y: "38%", size: 48, opacity: 0.3, off: 24.5 },
  { x: "58%", y: "74%", size: 66, opacity: 0.5, off: 25.8 },
  { x: "10%", y: "24%", size: 40, opacity: 0.3, off: 27.1 },
  { x: "76%", y: "58%", size: 42, opacity: 0.3, off: 28.4 },
  { x: "48%", y: "8%", size: 70, opacity: 0.5, off: 29.7 },
  { x: "30%", y: "70%", size: 56, opacity: 0.3, off: 31.0 },
  { x: "95%", y: "73%", size: 92, opacity: 1, off: 32.3 },
  { x: "6%", y: "96%", size: 64, opacity: 0.5, off: 33.6 },
  { x: "68%", y: "10%", size: 38, opacity: 0.3, off: 34.9 },
];
