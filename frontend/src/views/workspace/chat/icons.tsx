/** The conversation surfaces' icon set: one 16-unit grid, one 1.5 stroke,
 *  round joins — the same family as `ChatsIcon`, so the sidebar, the overlay
 *  strip and the library read as one instrument. */

type IconProps = { size?: number; className?: string };

function Glyph({ size = 16, className, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M8 3v10M3 8h10" />
    </Glyph>
  );
}

/** Sidebar toggle: a panel with its left column marked. */
export function PanelIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <rect x="2" y="3" width="12" height="10" rx="1" />
      <path d="M6 3v10" />
    </Glyph>
  );
}

export function PencilIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M11.5 2.5a1.4 1.4 0 0 1 2 2L5 13l-3 1 1-3 8.5-8.5Z" />
    </Glyph>
  );
}

export function ArchiveIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <rect x="2" y="3" width="12" height="3.5" rx="0.5" />
      <path d="M3.5 6.5V13h9V6.5M6.5 9h3" />
    </Glyph>
  );
}

export function RestoreIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M2 8a6 6 0 1 1 1.8 4.3" />
      <path d="M2 8V4.5M2 8h3.5" />
    </Glyph>
  );
}

/** Down to the end of a transcript. */
export function ArrowDownIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M8 3v10M3.5 8.5 8 13l4.5-4.5" />
    </Glyph>
  );
}

/** Points right; rotate with a class when a disclosure is open. */
export function ChevronIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M6 3.5 10.5 8 6 12.5" />
    </Glyph>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <Glyph {...props}>
      <path d="M4 4l8 8M12 4l-8 8" />
    </Glyph>
  );
}
