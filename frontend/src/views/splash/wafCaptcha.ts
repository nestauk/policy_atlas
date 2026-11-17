import { useEffect, useRef, useState, type RefObject } from "react";

/** The slice of the AWS WAF CAPTCHA SDK (`jsapi.js`) the form uses; the SDK ships no types. */
declare global {
  interface Window {
    AwsWafCaptcha?: {
      renderCaptcha(
        container: HTMLElement,
        options: {
          apiKey: string;
          onSuccess: (token: string) => void;
          onError?: (error: unknown) => void;
        },
      ): void;
    };
  }
}

export type WafCaptchaStatus = "idle" | "loading" | "ready" | "unavailable";

/** How long the script may take after the first interaction before the form says so. */
const LOAD_TIMEOUT_MS = 10_000;

/**
 * The firewall's CAPTCHA puzzle for the waitlist form (contract 064b W6).
 *
 * Inert unless both `VITE_WAF_CAPTCHA_*` values are set. The script loads on `arm()`,
 * which the form calls on its first focus, never on mount: a visitor who never touches
 * the form loads no third-party script.
 */
export function useWafCaptcha(container: RefObject<HTMLElement | null>) {
  // Read here, not at module scope, so `vi.stubEnv` in a test is seen.
  const scriptUrl = import.meta.env.VITE_WAF_CAPTCHA_SCRIPT_URL ?? "";
  const apiKey = import.meta.env.VITE_WAF_CAPTCHA_API_KEY ?? "";
  const configured = scriptUrl !== "" && apiKey !== "";

  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<WafCaptchaStatus>("idle");
  const armed = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const render = () => {
    const box = container.current;
    const sdk = window.AwsWafCaptcha;
    if (!box || !sdk) return;
    clearTimeout(timer.current);
    box.replaceChildren();
    // Before the call: the SDK may report success or an error synchronously.
    setStatus("ready");
    sdk.renderCaptcha(box, {
      apiKey,
      onSuccess: (solved) => setToken(solved),
      onError: () => setStatus("unavailable"),
    });
  };

  const arm = () => {
    if (!configured || armed.current) return;
    armed.current = true;
    if (window.AwsWafCaptcha) {
      render();
      return;
    }
    setStatus("loading");
    let script = document.head.querySelector<HTMLScriptElement>("script[data-waf-captcha]");
    if (!script) {
      script = document.createElement("script");
      // AWS returns the integration URL with a trailing slash.
      script.src = `${scriptUrl.replace(/\/+$/, "")}/jsapi.js`;
      script.async = true;
      script.dataset.wafCaptcha = "";
      document.head.append(script);
    }
    // A load after the timeout still renders, which clears the message.
    script.addEventListener("load", render, { once: true });
    script.addEventListener("error", () => setStatus("unavailable"), { once: true });
    timer.current = setTimeout(() => setStatus("unavailable"), LOAD_TIMEOUT_MS);
  };

  const reset = () => {
    setToken(null);
    render();
  };

  return { configured, token, status, arm, reset };
}
