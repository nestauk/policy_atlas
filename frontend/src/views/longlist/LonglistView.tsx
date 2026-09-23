import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import type { components } from "../../api/gen/types";
import { useAddOption, useExcludeOption, useIncludeOption } from "../../api/mutations";
import { useTask } from "../../api/queries";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { cn } from "../../ui/brand/cn";
import { isRunActive } from "../scopingActivity";
import { LonglistGrid } from "./LonglistGrid";
import {
  DO_NOTHING_AFTER,
  DO_NOTHING_BEFORE,
  DO_NOTHING_LINK,
  SCOPING_PASS_SENTENCE,
  originLabel,
  relationLabel,
  whereTriedFacetChips,
} from "./longlistPresentation";

type LonglistOut = components["schemas"]["LonglistOut"];
type OptionSummaryOut = components["schemas"]["OptionSummaryOut"];
type WhereTriedGroup = "where" | "comparable" | "other" | "unknown";
type ShowFilter = "all" | "included" | "excluded";

/** The setting facet shows this many chips before "more". */
const SETTING_FACET_LIMIT = 8;

const SHOW_FILTERS: { key: ShowFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "included", label: "Included" },
  { key: "excluded", label: "Excluded" },
];

const FACET_CHIP_CLASS =
  "cursor-pointer border px-2.5 py-1 text-caption font-semibold transition-colors";

function facetChipClass(active: boolean): string {
  return cn(
    FACET_CHIP_CLASS,
    active ? "border-blue bg-blue-tint text-blue" : "border-line-2 bg-paper text-grey hover:text-navy",
  );
}

function toggleInSet<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

/**
 * The longlist's list view (contract deliverable 9, plan S13): the header
 * counts, the Show/Setting/Where-tried facets, theme sections with option
 * rows, the "Do nothing" reference, and a List · Grid toggle that swaps in
 * `LonglistGrid` (D12) in place of the theme sections.
 */
export function LonglistView({ taskId, longlist }: { taskId: string; longlist: LonglistOut }) {
  const task = useTask(taskId);
  const addOption = useAddOption(taskId);
  const excludeOption = useExcludeOption(taskId);
  const includeOption = useIncludeOption(taskId);

  const [show, setShow] = useState<ShowFilter>("all");
  const [settingsFilter, setSettingsFilter] = useState<Set<string>>(new Set());
  const [whereFilter, setWhereFilter] = useState<Set<WhereTriedGroup>>(new Set());
  const [mode, setMode] = useState<"list" | "grid">("list");
  const [addText, setAddText] = useState("");
  const [excludingId, setExcludingId] = useState<string | null>(null);
  const [excludeReason, setExcludeReason] = useState("");

  const options = longlist.options ?? [];
  const optionsById = new Map(options.map((option) => [option.option_id, option]));

  // Settings are source-named and long-tailed (a live NEET longlist carried
  // 28 of them): the facet shows the commonest few and folds the rest.
  const settingCounts = new Map<string, number>();
  for (const option of options) {
    for (const setting of option.settings ?? []) {
      settingCounts.set(setting, (settingCounts.get(setting) ?? 0) + 1);
    }
  }
  const allSettings = [...settingCounts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([setting]) => setting);
  const [allSettingsShown, setAllSettingsShown] = useState(false);
  const shownSettings =
    allSettingsShown || allSettings.length <= SETTING_FACET_LIMIT
      ? allSettings
      : allSettings.filter((setting) => settingsFilter.has(setting) || allSettings.indexOf(setting) < SETTING_FACET_LIMIT);
  const hiddenSettings = allSettings.length - shownSettings.length;
  const whereChips = whereTriedFacetChips(longlist.where_label);

  const passesFilters = (option: OptionSummaryOut): boolean => {
    if (show === "included" && option.state !== "included") return false;
    if (show === "excluded" && option.state !== "excluded") return false;
    if (settingsFilter.size > 0) {
      const optionSettings = option.settings ?? [];
      if (![...settingsFilter].some((setting) => optionSettings.includes(setting))) return false;
    }
    if (whereFilter.size > 0) {
      const whereTried = option.where_tried;
      if (![...whereFilter].some((group) => (whereTried[group] ?? 0) > 0)) return false;
    }
    return true;
  };

  const walkActive = isRunActive(task.data);

  const handleAddOption = (event: FormEvent) => {
    event.preventDefault();
    const text = addText.trim();
    if (text === "" || addOption.isPending || walkActive) return;
    addOption.mutate({ text }, { onSuccess: () => setAddText("") });
  };

  const submitExclude = (optionId: string) => {
    const reason = excludeReason.trim();
    if (reason === "" || excludeOption.isPending) return;
    excludeOption.mutate(
      { optionId, reason },
      {
        onSuccess: () => {
          setExcludingId(null);
          setExcludeReason("");
        },
      },
    );
  };

  const handleInclude = (optionId: string) => {
    if (includeOption.isPending) return;
    includeOption.mutate({ optionId });
  };

  const renderOptionRow = (option: OptionSummaryOut) => (
    <li key={option.option_id} className="border-b border-line py-4 last:border-b-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link
          to={`/tasks/${taskId}/options/${option.option_id}`}
          className="text-lead font-bold text-navy hover:underline"
        >
          {scrub(option.name)}
        </Link>
        <Chip tone="soft">{originLabel(option.origin, option.document_count)}</Chip>
      </div>
      <p className="mt-1 text-body text-grey">{scrub(option.description)}</p>
      {(option.outcomes_served?.length ?? 0) > 0 && (
        <p className="mt-1 text-caption text-grey">{option.outcomes_served?.map((o) => scrub(o)).join(", ")}</p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-body">
        {option.state === "excluded" && option.exclusion != null && (
          <Chip tone="red">excluded: breaks "{scrub(option.exclusion.constraint)}"</Chip>
        )}
        {option.no_in_scope_evidence && <Chip tone="yellow">no in-scope evidence</Chip>}
        {option.abstract_only && <Chip tone="soft">abstract only</Chip>}
        {option.search_pending ? (
          <Chip tone="soft">searching for its evidence…</Chip>
        ) : (
          option.is_entrant_with_no_documents && <Chip tone="soft">no documents found yet</Chip>
        )}
        {(option.relations ?? []).map((relation) => (
          <Chip key={`${relation.kind}-${relation.other_option_id}`} tone="soft">
            {relationLabel(relation)}
          </Chip>
        ))}
      </div>
      <div className="mt-2.5">
        {option.state === "included" ? (
          excludingId === option.option_id ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                autoFocus
                value={excludeReason}
                onChange={(event) => setExcludeReason(event.target.value)}
                placeholder="Why exclude this option?"
                className="flex-1 border border-line-2 bg-paper px-3 py-1.5 text-body focus-visible:outline-2 focus-visible:outline-blue"
              />
              <Button
                variant="secondary"
                size="sm"
                disabled={excludeReason.trim() === "" || excludeOption.isPending}
                onClick={() => submitExclude(option.option_id)}
              >
                Exclude
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setExcludingId(null)}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button variant="secondary" size="sm" onClick={() => setExcludingId(option.option_id)}>
              Exclude
            </Button>
          )
        ) : (
          <Button
            variant="secondary"
            size="sm"
            disabled={includeOption.isPending}
            onClick={() => handleInclude(option.option_id)}
          >
            Include again
          </Button>
        )}
      </div>
    </li>
  );

  const themeSections = (longlist.themes ?? []).map((theme) => {
    const themeOptions = (theme.option_ids ?? [])
      .map((id) => optionsById.get(id))
      .filter((option): option is OptionSummaryOut => option !== undefined)
      .filter(passesFilters);
    if (themeOptions.length === 0) return null;
    return (
      <details key={theme.theme_id} open className="border-b border-line-2 py-4 last:border-b-0">
        <summary className="cursor-pointer list-none">
          <span className="text-lead font-bold text-navy">{scrub(theme.name)}</span>
          <span className="ml-2 text-body text-grey">{themeOptions.length} options</span>
          {theme.description !== "" && <p className="mt-0.5 text-body text-grey">{scrub(theme.description)}</p>}
        </summary>
        <ul role="list" className="mt-2">
          {themeOptions.map(renderOptionRow)}
        </ul>
      </details>
    );
  });

  const unthemedOptions = (longlist.unthemed_option_ids ?? [])
    .map((id) => optionsById.get(id))
    .filter((option): option is OptionSummaryOut => option !== undefined)
    .filter(passesFilters);

  return (
    <main className="py-8">
      <header className="mb-5">
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone="blue">{scrub(longlist.depth_label)}</Chip>
          <span className="text-body text-grey">{SCOPING_PASS_SENTENCE}</span>
        </div>
        <p className="mt-2 text-body text-grey">
          {longlist.counts.options} options · {longlist.counts.themes} themes · {longlist.counts.included}{" "}
          included · {longlist.counts.no_in_scope} with no in-scope evidence · {longlist.counts.excluded}{" "}
          excluded · {longlist.counts.unclustered} records unclustered
        </p>
      </header>

      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          <div role="group" aria-label="Show" className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-caption font-semibold uppercase tracking-wide text-grey">Show</span>
            {SHOW_FILTERS.map((filter) => (
              <button
                key={filter.key}
                type="button"
                aria-pressed={show === filter.key}
                onClick={() => setShow(filter.key)}
                className={facetChipClass(show === filter.key)}
              >
                {filter.label}
              </button>
            ))}
          </div>
          {allSettings.length > 0 && (
            <div role="group" aria-label="Setting" className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-caption font-semibold uppercase tracking-wide text-grey">Setting</span>
              {shownSettings.map((setting) => (
                <button
                  key={setting}
                  type="button"
                  aria-pressed={settingsFilter.has(setting)}
                  onClick={() => setSettingsFilter((current) => toggleInSet(current, setting))}
                  className={facetChipClass(settingsFilter.has(setting))}
                >
                  {scrub(setting)}
                </button>
              ))}
              {hiddenSettings > 0 && (
                <button
                  type="button"
                  onClick={() => setAllSettingsShown(true)}
                  className="text-caption font-semibold text-blue hover:underline"
                >
                  +{hiddenSettings} more
                </button>
              )}
              {allSettingsShown && allSettings.length > SETTING_FACET_LIMIT && (
                <button
                  type="button"
                  onClick={() => setAllSettingsShown(false)}
                  className="text-caption font-semibold text-blue hover:underline"
                >
                  fewer
                </button>
              )}
            </div>
          )}
          <div role="group" aria-label="Where tried" className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-caption font-semibold uppercase tracking-wide text-grey">Where tried</span>
            {whereChips.map((chip) => (
              <button
                key={chip.group}
                type="button"
                aria-pressed={whereFilter.has(chip.group)}
                onClick={() => setWhereFilter((current) => toggleInSet(current, chip.group))}
                className={facetChipClass(whereFilter.has(chip.group))}
              >
                {scrub(chip.label)}
              </button>
            ))}
          </div>
        </div>
        <div role="group" aria-label="View" className="flex gap-1.5">
          <button
            type="button"
            aria-pressed={mode === "list"}
            onClick={() => setMode("list")}
            className={facetChipClass(mode === "list")}
          >
            List
          </button>
          <button
            type="button"
            aria-pressed={mode === "grid"}
            onClick={() => setMode("grid")}
            className={facetChipClass(mode === "grid")}
          >
            Grid
          </button>
        </div>
      </div>

      <p className="mb-5 text-body text-ink">
        {DO_NOTHING_BEFORE}
        <Link to={`/tasks/${taskId}/result?view=baseline`} className="font-semibold text-blue hover:underline">
          {DO_NOTHING_LINK}
        </Link>
        {DO_NOTHING_AFTER}
      </p>

      <form onSubmit={handleAddOption} className="mb-6 flex flex-wrap items-center gap-2">
        <label htmlFor="longlist-add-option" className="sr-only">
          Add an option
        </label>
        <input
          id="longlist-add-option"
          value={addText}
          onChange={(event) => setAddText(event.target.value)}
          placeholder="An option of your own, in a few words"
          disabled={walkActive}
          className="w-full max-w-md border border-line-2 bg-paper px-3 py-1.5 text-body focus-visible:outline-2 focus-visible:outline-blue disabled:bg-paper-2"
        />
        <Button type="submit" variant="secondary" size="sm" disabled={addText.trim() === "" || addOption.isPending || walkActive}>
          Add an option
        </Button>
      </form>

      {mode === "grid" ? (
        <LonglistGrid taskId={taskId} longlist={longlist} />
      ) : (
        <section>
          {themeSections}
          {unthemedOptions.length > 0 && (
            <details open className="border-b border-line-2 py-4 last:border-b-0">
              <summary className="cursor-pointer list-none">
                <span className="text-lead font-bold text-navy">No theme</span>
                <span className="ml-2 text-body text-grey">{unthemedOptions.length} options</span>
              </summary>
              <ul role="list" className="mt-2">
                {unthemedOptions.map(renderOptionRow)}
              </ul>
            </details>
          )}
        </section>
      )}
    </main>
  );
}
