/**
 * Ask once for permission to show browser alerts when a task's work finishes
 * (see views/finishAlerts.ts). Call it from a click: browsers only ask then.
 */
export function askForFinishAlerts(): void {
  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    void Notification.requestPermission();
  }
}
