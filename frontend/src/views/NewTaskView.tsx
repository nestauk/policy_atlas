import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { usePortfolios } from "../api/queries";
import { useCreateTask } from "../api/mutations";
import { useDocumentTitle } from "../lib/title";
import { COPY, PROJECT, TASK } from "../lib/vocabulary";
import { Button } from "../ui/brand/Button";
import { Card } from "../ui/brand/Card";

/**
 * The kinds of work the system can do.
 *
 * Three are listed but cannot run. Listing them is the honest move: the shape
 * of the product is visible, and a person can tell that scoping options is
 * planned rather than forgotten. They are not links and have no route, so
 * there is nothing to click that would fail.
 */
const CAPABILITIES = [
  {
    key: "evidence_base",
    name: "Evidence search",
    description: "Find, screen and synthesise research evidence on a policy question.",
    available: true,
  },
  {
    key: "scoping_policy_options",
    name: "Scoping policy options",
    description: "Lay out the options open to a policymaker and what each would involve.",
    available: false,
  },
  {
    key: "theory_of_change",
    name: "Theory of change",
    description: "Trace how an intervention is meant to lead to its intended outcome.",
    available: false,
  },
  {
    key: "map_stakeholders",
    name: "Map stakeholders",
    description: "Identify who is affected by a policy area and how they are positioned.",
    available: false,
  },
] as const;

const EXAMPLE_QUESTION =
  "What works to reduce childhood obesity in primary schools?";

/** Step one: pick a kind of work. Only one of the four can run. */
function CapabilityList({ onPick }: { onPick: () => void }) {
  return (
    <ul role="list" className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
      {CAPABILITIES.map((capability) =>
        capability.available ? (
          <li key={capability.key}>
            <button
              type="button"
              onClick={onPick}
              className="h-full w-full cursor-pointer border border-line-2 bg-paper p-5 text-left hover:border-navy focus-visible:outline-2 focus-visible:outline-blue"
            >
              <span className="block text-body font-bold text-navy">{capability.name}</span>
              <span className="mt-1.5 block text-body text-grey">{capability.description}</span>
            </button>
          </li>
        ) : (
          <li key={capability.key}>
            {/* Not a button and not focusable: a control whose only possible
                outcome is failure should not be reachable at all. */}
            <div
              aria-disabled="true"
              className="h-full border border-dashed border-line-2 bg-paper-2 p-5 select-none"
            >
              <span className="flex items-center gap-2">
                <span className="text-body font-bold text-line-2">{capability.name}</span>
                <span className="border border-line-2 px-1.5 py-0.5 text-caption font-bold uppercase tracking-[0.06em] text-grey">
                  {COPY.comingSoon}
                </span>
              </span>
              <span className="mt-1.5 block text-body text-line-2">{capability.description}</span>
            </div>
          </li>
        ),
      )}
    </ul>
  );
}

/** Step two: the question, and as little else as possible beside it. */
function QuestionForm() {
  const [question, setQuestion] = useState("");
  const [portfolioId, setPortfolioId] = useState("");
  const portfolios = usePortfolios();
  const create = useCreateTask();
  const navigate = useNavigate();
  const canSend = question.trim().length > 0 && !create.isPending;

  const submit = () => {
    if (!canSend) return;
    create.mutate(
      { question, portfolioId: portfolioId === "" ? null : portfolioId },
      { onSuccess: (project) => void navigate(`/projects/${project.project_id}`) },
    );
  };

  return (
    <form
      className="mt-10"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <p className="text-caption font-bold uppercase tracking-[0.06em] text-grey">
        Evidence search
      </p>
      <h1 className="mt-2 font-display text-title font-extrabold tracking-[-0.5px] text-navy">
        What do you need evidence on?
      </h1>
      <p className="mt-3 max-w-prose text-lead text-grey">
        Ask it the way you would ask a colleague. You will agree the plan before
        anything runs.
      </p>

      <div className="relative mt-8">
        <label className="sr-only" htmlFor="new-task-question">
          Your question
        </label>
        <textarea
          id="new-task-question"
          autoFocus
          rows={5}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          className="w-full resize-none border border-line-2 bg-paper p-4 pr-28 text-body text-navy focus-visible:outline-2 focus-visible:outline-blue"
        />
        <div className="absolute right-3 bottom-3">
          <Button type="submit" size="sm" disabled={!canSend}>
            {create.isPending ? "Starting…" : "Start"}
          </Button>
        </div>
      </div>
      <p className="mt-2 text-caption text-grey">
        Enter to send · Shift + Enter for a new line
      </p>

      {question.trim() === "" && (
        <p className="mt-6 text-body text-grey">
          For example:{" "}
          <button
            type="button"
            onClick={() => setQuestion(EXAMPLE_QUESTION)}
            className="cursor-pointer text-left font-semibold text-blue hover:underline"
          >
            {EXAMPLE_QUESTION}
          </button>
        </p>
      )}

      {(portfolios.data?.data.length ?? 0) > 0 && (
        <div className="mt-8 flex items-center gap-3">
          <label className="text-meta text-grey" htmlFor="new-task-portfolio">
            Add to a {PROJECT.lower}
          </label>
          <select
            id="new-task-portfolio"
            value={portfolioId}
            onChange={(event) => setPortfolioId(event.target.value)}
            className="border border-line-2 bg-paper px-2 py-1.5 text-meta text-navy focus-visible:outline-2 focus-visible:outline-blue"
          >
            <option value="">{COPY.noProject}</option>
            {portfolios.data?.data.map((portfolio) => (
              <option key={portfolio.portfolio_id} value={portfolio.portfolio_id}>
                {portfolio.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {create.isError && (
        <Card role="alert" className="mt-6 max-w-md p-4 text-body text-navy">
          The {TASK.lower} couldn't be started. Try again.
        </Card>
      )}
    </form>
  );
}

/** New task: choose a kind of work, then ask the question. */
export function NewTaskView() {
  useDocumentTitle(COPY.newTask);
  const [searchParams, setSearchParams] = useSearchParams();
  // The chosen capability is URL-addressable, like every other view state.
  const picked = searchParams.get("capability") === "evidence_base";

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-10">
      {picked ? (
        <QuestionForm />
      ) : (
        <>
          <h1 className="font-display text-title font-extrabold tracking-[-0.5px] text-navy">
            {COPY.newTask}
          </h1>
          <p className="mt-3 max-w-prose text-lead text-grey">
            What kind of work do you want to start?
          </p>
          <CapabilityList onPick={() => setSearchParams({ capability: "evidence_base" })} />
        </>
      )}
    </main>
  );
}
