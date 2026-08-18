/** Stacked speech bubbles: the conversations-library glyph, shared by the
 *  overlay `ConversationTabs` and the side-panel library button. */
export function ChatsIcon({ size }: { size: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M5 4h9v7h-3l-2 2-2-2H5z" />
      <path d="M3 8H2V1h9v1" />
    </svg>
  );
}
