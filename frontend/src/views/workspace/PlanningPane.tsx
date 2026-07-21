import { useState } from "react";

import { usePlanningTurn, useStartRun } from "../../api/mutations";
import type { components } from "../../api/gen/types";
import { scrub } from "../../lib/scrub";
import { Button } from "../../ui/brand/Button";
import { Chip } from "../../ui/brand/Chip";
import { Divider, PaneHeading } from "../../ui/brand/Card";

type PlanDraft = components["schemas"]["PlanDraft"];

interface Turn {
  role: "user" | "planner";
  text: string;
}

function PlanDisclosure({ plan }: { plan: PlanDraft }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-line bg-paper-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="flex w-full cursor-pointer items-center justify-between px-3.5 py-2.5 text-left text-[12.5px] font-bold text-navy hover:bg-blue-tint-2"
      >
        View plan
        <span aria-hidden="true" className="text-blue">
          {open ? "▴" : "▾"}
        </span>
      </button>
      {open && (
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 border-t border-line px-3.5 py-3 text-[12.5px] sm:grid-cols-2">
          {(
            [
              ["Question", plan.question],
              ["Search effort", plan.search_effort],
              ["Analysis depth", plan.analysis_depth],
              ["Sources", plan.backend_scope],
              ["Steering", plan.steering_mode],
              ["Expected shape", plan.expected_artefact_shape],
              ["Time", plan.time_band],
            ] as const
          )
            .filter(([, value]) => value !== null && value !== undefined && value !== "")
            .map(([label, value]) => (
              <div key={label}>
                <dt className="font-semibold text-grey">{label}</dt>
                <dd className="mt-0.5 text-ink">{scrub(String(value))}</dd>
              </div>
            ))}
          {plan.scoping_notes !== null &&
            plan.scoping_notes !== undefined &&
            plan.scoping_notes.length > 0 && (
              <div className="sm:col-span-2">
                <dt className="font-semibold text-grey">Scoping notes</dt>
                <dd className="mt-0.5">
                  <ul className="list-disc pl-4 text-ink">
                    {plan.scoping_notes.map((note) => (
                      <li key={note}>{scrub(note)}</li>
                    ))}
                  </ul>
                </dd>
              </div>
            )}
          {plan.steps !== null && plan.steps !== undefined && plan.steps.length > 0 && (
            <div className="sm:col-span-2">
              <dt className="font-semibold text-grey">Steps</dt>
              <dd className="mt-1 flex flex-wrap gap-1.5">
                {plan.steps.map((step) => (
                  <Chip key={step.stage} tone="soft">
                    {scrub(step.label)}
                  </Chip>
                ))}
              </dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}

/**
 * The planning conversation: real planner turns, tappable suggestion chips,
 * the plan disclosure, and "Start the analysis" once the draft validates
 * ready. Drafts are process-local server-side — a restart loses an
 * in-flight conversation honestly (the approved plan object is durable).
 */
export function PlanningPane({ projectId }: { projectId: string }) {
  const turn = usePlanningTurn(projectId);
  const startRun = useStartRun(projectId);
  const [thread, setThread] = useState<Turn[]>([]);
  const [message, setMessage] = useState("");
  const [plan, setPlan] = useState<PlanDraft | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [startNotice, setStartNotice] = useState<string | null>(null);

  const send = (text: string) => {
    const trimmed = text.trim();
    if (trimmed.length === 0 || turn.isPending) return;
    setThread((current) => [...current, { role: "user", text: trimmed }]);
    setMessage("");
    turn.mutate(trimmed, {
      onSuccess: (result) => {
        setThread((current) => [...current, { role: "planner", text: result.reply }]);
        setPlan(result.plan);
        setSuggestions(result.suggestions ?? []);
      },
      onError: (error) => {
        const code = (error as { code?: string }).code;
        setThread((current) => [
          ...current,
          {
            role: "planner",
            text:
              code === "planning_turn_in_progress"
                ? "A planning turn is already in progress — give it a moment, then try again."
                : "That turn couldn't be processed. Your draft so far is unchanged — try again.",
          },
        ]);
      },
    });
  };

  return (
    <section aria-label="Planning conversation" className="flex h-full flex-col">
      <PaneHeading>Plan the analysis</PaneHeading>
      <Divider />
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {thread.length === 0 && (
          <div role="status" className="text-[12.5px] leading-relaxed text-grey">
            <p>
              Describe the policy question you need evidence for. The planner refines it
              with you into an analysis plan you approve before anything runs.
            </p>
            <p className="mt-2 text-[11.5px]">
              Drafts live for this session only — an approved plan is kept.
            </p>
          </div>
        )}
        {thread.map((entry, index) => (
          <div
            key={index}
            className={
              entry.role === "user"
                ? "ml-8 border border-blue-tint bg-blue-tint-2 px-3.5 py-2.5"
                : "mr-8 border border-line bg-paper px-3.5 py-2.5"
            }
          >
            <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink">
              {scrub(entry.text)}
            </p>
          </div>
        ))}
        {turn.isPending && (
          <p role="status" className="mr-8 animate-pulse px-3.5 text-[12.5px] text-grey">
            Planning…
          </p>
        )}
        {suggestions.length > 0 && !turn.isPending && (
          <div className="flex flex-wrap gap-1.5">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => send(suggestion)}
                className="cursor-pointer border border-[#c7c7ff] bg-blue-tint px-2.5 py-1 text-[11.5px] font-semibold text-blue hover:bg-blue-tint-2 focus-visible:outline-2 focus-visible:outline-blue"
              >
                {scrub(suggestion)}
              </button>
            ))}
          </div>
        )}
        {plan !== null && <PlanDisclosure plan={plan} />}
      </div>

      <div className="border-t border-line px-4 py-3">
        <form
          className="flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            send(message);
          }}
        >
          <label className="sr-only" htmlFor="planning-message">
            Message the planner
          </label>
          <input
            id="planning-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="What do you need evidence on?"
            className="flex-1 border border-line-2 bg-paper px-3 py-2.5 text-[13px] focus-visible:outline-2 focus-visible:outline-blue"
          />
          <Button type="submit" variant="secondary" disabled={turn.isPending}>
            Send
          </Button>
        </form>
        {plan?.ready === true && (
          <div className="mt-3 flex items-center gap-3">
            <Button
              disabled={startRun.isPending}
              onClick={() => {
                setStartNotice(null);
                startRun.mutate(undefined, {
                  onError: (error) => {
                    const code = (error as { code?: string }).code;
                    setStartNotice(
                      code === "run_active"
                        ? "An analysis is already active on this project."
                        : code === "capacity"
                          ? "The server is at capacity — try again shortly."
                          : "The analysis couldn't start. Try again.",
                    );
                  },
                });
              }}
            >
              Start the analysis
            </Button>
            {startNotice !== null && (
              <p role="alert" className="text-xs text-red">
                {startNotice}
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
