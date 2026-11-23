/**
 * The viewport lock of a task view.
 *
 * A task view fills the viewport: the navigation and the tab bar stay put and
 * only the pane between them scrolls. That needs height. At 400% zoom a
 * 1280 by 1024 window is 320 by 256 CSS pixels, and the navigation and tab
 * bar alone are taller than that, so a locked page would show no content at
 * all (WCAG 1.4.10 Reflow). Below 30rem of height the lock is off: the page
 * is as tall as its content and the document scrolls, as a list page does.
 */

/** On the task shell: fills the viewport and clips, when the viewport is tall enough. */
export const TASK_LOCK_SHELL_CLASS = "min-h-svh [@media(min-height:30rem)]:h-svh [@media(min-height:30rem)]:overflow-hidden";

/** On `<html>` while a task view shows: no document scroll, when the viewport is tall enough. */
export const TASK_LOCK_ROOT_CLASS = "[@media(min-height:30rem)]:overflow-hidden";
