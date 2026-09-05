/** The empty chat: an invitation and up to three starter questions drawn from
 *  the report's sections. Shared by a real chat with no turns yet and by a
 *  draft chat that has no row at all (038 V8).
 *
 * Args:
 *   props: `message` (the invitation, or an error line), the starter
 *     `questions`, and `onAsk`, called with the question chosen.
 *
 * Returns:
 *   The centred invitation block.
 */
export function ChatEmptyState({
  message,
  questions,
  onAsk,
}: {
  message: string;
  questions: readonly string[];
  onAsk: (question: string) => void;
}) {
  return (
    <div className="space-y-2 py-8">
      <p className="text-body text-grey">{message}</p>
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          onClick={() => onAsk(question)}
          className="block text-left text-meta font-semibold text-blue hover:underline"
        >
          {question}
        </button>
      ))}
    </div>
  );
}

/** Starter questions for a task's report sections (the first three). */
export function starterQuestions(sectionTitles: readonly string[]): string[] {
  return sectionTitles.slice(0, 3).map((title) => `Tell me more about "${title}"`);
}
