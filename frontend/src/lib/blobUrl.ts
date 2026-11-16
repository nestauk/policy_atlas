/**
 * One browser address per file (an uploaded diagram), kept while the page is open.
 *
 * Making a fresh `URL.createObjectURL` per render and revoking it on unmount
 * breaks the picture when a component remounts (a tab switch, or React's
 * development double mount): the address is revoked before the image loads.
 */
// ponytail: never revoked; a few diagrams per session. Revoke on task close if many files appear.
const urls = new WeakMap<Blob, string>();

export function blobUrl(blob: Blob): string {
  let url = urls.get(blob);
  if (url === undefined) {
    url = URL.createObjectURL(blob);
    urls.set(blob, url);
  }
  return url;
}
