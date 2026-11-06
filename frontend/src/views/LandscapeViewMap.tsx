import { useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { useNavigate } from "react-router";
import { geoNaturalEarth1, geoPath, type ExtendedFeature, type ExtendedFeatureCollection } from "d3-geo";
import { feature } from "topojson-client";
import topology from "world-atlas/countries-110m.json";

import { scrub } from "../lib/scrub";

/* ---------------------------------------------------------------------------
 * Where sources were published, as a map (task 058, round 11; the owner
 * asked twice, the lead chose the dependencies). A choropleth of publisher
 * countries on the Natural Earth projection, Navy by count, countries with
 * none in Line 2. The list beside it stays the default and the keyboard's
 * path: the map is for the eye, so its countries take no focus.
 *
 * This module is loaded with `React.lazy`, so the Landscape page does not
 * carry the atlas until the reader asks for the map.
 * ------------------------------------------------------------------------- */

type CountryFeature = ExtendedFeature<GeoJSON.Geometry | null, { name: string }>;

/** The countries of the atlas, Antarctica left out (it holds no publisher
 *  and would take a sixth of the frame). */
const COUNTRIES: CountryFeature[] = (
  feature(topology, "countries") as unknown as ExtendedFeatureCollection<CountryFeature>
).features.filter((country) => country.properties.name !== "Antarctica");

/** The frame's width in SVG units; its height follows the projection. */
const WIDTH = 960;
const projection = geoNaturalEarth1().fitWidth(WIDTH, { type: "FeatureCollection", features: COUNTRIES });
const path = geoPath(projection);
const [[, top], [, bottom]] = path.bounds({ type: "FeatureCollection", features: COUNTRIES });
const HEIGHT = Math.ceil(bottom - top);

/** A name reduced for matching: lower case, no accents, no "(the …)" or
 *  ", Republic of" tail, no leading "the", single spaces. */
export function matchKey(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\([^)]*\)/g, "")
    .split(",")[0]
    .replace(/^the\s+/, "")
    .replace(/[^a-z0-9' -]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** The countries the server names in its own words (ISO names with the
 *  common-use overrides) where the atlas abbreviates or differs. */
const ALIASES: Record<string, string> = {
  "united states": "United States of America",
  usa: "United States of America",
  "czech republic": "Czechia",
  "bosnia and herzegovina": "Bosnia and Herz.",
  "central african republic": "Central African Rep.",
  "dominican republic": "Dominican Rep.",
  "equatorial guinea": "Eq. Guinea",
  "democratic republic of the congo": "Dem. Rep. Congo",
  "dr congo": "Dem. Rep. Congo",
  "republic of the congo": "Congo",
  eswatini: "eSwatini",
  swaziland: "eSwatini",
  "solomon islands": "Solomon Is.",
  "falkland islands": "Falkland Is.",
  "south sudan": "S. Sudan",
  "western sahara": "W. Sahara",
  "ivory coast": "Côte d'Ivoire",
  "north macedonia": "Macedonia",
  "viet nam": "Vietnam",
  "lao people's democratic republic": "Laos",
  "syrian arab republic": "Syria",
  "russian federation": "Russia",
  "republic of korea": "South Korea",
  korea: "South Korea",
  "democratic people's republic of korea": "North Korea",
  "brunei darussalam": "Brunei",
  turkiye: "Turkey",
  "great britain": "United Kingdom",
  uk: "United Kingdom",
  "east timor": "Timor-Leste",
};

const BY_KEY = new Map(COUNTRIES.map((country) => [matchKey(country.properties.name), country.properties.name]));

/**
 * The atlas's name for a publisher country, or `null` when the atlas has no
 * shape for it (a region such as "Global" or "EU", or a country too small
 * for the 1:110m map, such as Singapore).
 *
 * Args:
 *   country: The country as the landscape names it.
 */
export function atlasName(country: string): string | null {
  const key = matchKey(country);
  return ALIASES[key] ?? BY_KEY.get(key) ?? null;
}

/** The sequential scale's five steps: Navy mixed into Paper, the lightest
 *  still clear of Line 2 (a country with none), evenly spaced in lightness. */
export const MAP_STEPS = [35, 51, 67, 84, 100] as const;

/**
 * The step a count takes, 0 to 4, on a log scale from 1 to the largest
 * count, so one dominant country does not leave every other one in the
 * lightest step.
 *
 * Args:
 *   count: The country's sources (at least 1).
 *   max: The largest count on the map.
 */
export function mapStep(count: number, max: number): number {
  if (max <= 1) return MAP_STEPS.length - 1;
  const share = Math.log(Math.max(1, count)) / Math.log(max);
  return Math.min(MAP_STEPS.length - 1, Math.floor(share * MAP_STEPS.length));
}

const stepFill = (step: number) => `color-mix(in oklab, var(--color-navy) ${MAP_STEPS[step]}%, var(--color-paper))`;

/** One publisher country on the map: its name as the landscape says it. */
export type MapCountry = { country: string; count: number };

/**
 * The publisher countries as a choropleth (round 11). A country with
 * sources is Navy by its count; one with none is Line 2. Under a fine
 * pointer a country with sources turns Electric Blue and a tooltip reads
 * "United Kingdom · 23"; a press opens All sources for it, as its row in
 * the list does. The names the atlas cannot place are listed under the map
 * ("Not on the map: Global, EU"). Nothing animates.
 *
 * Args:
 *   countries: The countries and their counts ("Not reported" left out).
 *   caption: The section's heading, the map's accessible name.
 *   hrefFor: Where a country leads, when it leads anywhere.
 */
export default function PublisherMap({
  countries,
  caption,
  hrefFor,
}: {
  countries: readonly MapCountry[];
  caption: string;
  hrefFor: (country: string) => string | undefined;
}) {
  const navigate = useNavigate();
  const frame = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ name: string; x: number; y: number } | null>(null);

  const placed = new Map<string, MapCountry>();
  const unplaced: string[] = [];
  for (const entry of countries) {
    const name = atlasName(entry.country);
    if (name === null) unplaced.push(scrub(entry.country));
    else {
      const before = placed.get(name);
      placed.set(name, { country: before?.country ?? entry.country, count: (before?.count ?? 0) + entry.count });
    }
  }
  const max = Math.max(1, ...[...placed.values()].map((entry) => entry.count));
  const hovered = hover !== null ? placed.get(hover.name) : undefined;

  const onMove = (event: PointerEvent<SVGPathElement>, name: string) => {
    if (event.pointerType !== "mouse") return;
    const box = frame.current?.getBoundingClientRect();
    if (box === undefined) return;
    setHover({ name, x: event.clientX - box.left, y: event.clientY - box.top });
  };

  return (
    <div className="publisher-map">
      <div ref={frame} className="publisher-map__frame" onPointerLeave={() => setHover(null)}>
        <svg
          viewBox={`0 ${Math.floor(top)} ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={caption}
          className="publisher-map__svg"
        >
          {COUNTRIES.map((country) => {
            const name = country.properties.name;
            const entry = placed.get(name);
            const href = entry !== undefined ? hrefFor(entry.country) : undefined;
            return (
              <path
                key={name}
                d={path(country) ?? ""}
                className="publisher-map__country"
                data-country={entry?.country}
                data-link={href !== undefined ? "" : undefined}
                data-hover={hover?.name === name && entry !== undefined ? "" : undefined}
                style={entry !== undefined ? ({ "--fill": stepFill(mapStep(entry.count, max)) } as CSSProperties) : undefined}
                onPointerMove={entry !== undefined ? (event) => onMove(event, name) : undefined}
                onPointerLeave={() => setHover(null)}
                onClick={href !== undefined ? () => void navigate(href) : undefined}
              />
            );
          })}
        </svg>
        {hovered !== undefined && hover !== null && (
          <span
            role="tooltip"
            className="publisher-map__tooltip"
            style={{ left: hover.x, top: hover.y }}
          >
            {scrub(hovered.country)} · <span className="tabular-nums">{hovered.count}</span>
          </span>
        )}
      </div>
      <div className="publisher-map__legend" aria-hidden="true">
        <span className="tabular-nums">1</span>
        {MAP_STEPS.map((_, step) => (
          <span key={step} className="publisher-map__swatch" style={{ backgroundColor: stepFill(step) }} />
        ))}
        <span className="tabular-nums">{max}</span>
      </div>
      {unplaced.length > 0 && (
        <p className="mt-2 text-meta text-grey" data-testid="not-on-map">
          Not on the map: {unplaced.join(", ")}
        </p>
      )}
    </div>
  );
}
