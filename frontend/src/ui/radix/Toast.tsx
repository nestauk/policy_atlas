import * as ToastPrimitive from "@radix-ui/react-toast";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { cn } from "../brand/cn";

/*
 * Toast (Radix copy-in) — the 500-error surface and transient confirmations.
 * Radix owns the a11y live region, swipe dismiss and timers.
 */

type ToastTone = "default" | "error";

interface ToastMessage {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
  action?: { label: string; onClick: () => void };
}

interface ToastApi {
  toast: (message: Omit<ToastMessage, "id">) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

/** Access the app toast API. Must be inside ToastProvider. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (api === null) {
    throw new Error("useToast requires a ToastProvider ancestor");
  }
  return api;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([]);

  const toast = useCallback((message: Omit<ToastMessage, "id">) => {
    setMessages((current) => [...current, { ...message, id: Date.now() + current.length }]);
  }, []);

  const api = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={api}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}
        {messages.map((message) => (
          <ToastPrimitive.Root
            key={message.id}
            duration={message.tone === "error" ? 8000 : 4000}
            onOpenChange={(open) => {
              if (!open) {
                setMessages((current) => current.filter((m) => m.id !== message.id));
              }
            }}
            className={cn(
              "flex items-start gap-3 border bg-paper p-4 shadow-[0_10px_30px_rgba(15,41,74,0.14)]",
              message.tone === "error" ? "border-red" : "border-line-2",
            )}
          >
            <div className="flex-1">
              <ToastPrimitive.Title className="text-meta font-bold text-navy">
                {message.title}
              </ToastPrimitive.Title>
              {message.description !== undefined && (
                <ToastPrimitive.Description className="mt-1 text-meta text-grey">
                  {message.description}
                </ToastPrimitive.Description>
              )}
            </div>
            {message.action !== undefined && (
              <ToastPrimitive.Action altText={message.action.label} asChild>
                <button
                  type="button"
                  onClick={message.action.onClick}
                  className="cursor-pointer text-meta font-bold text-blue hover:underline"
                >
                  {message.action.label}
                </button>
              </ToastPrimitive.Action>
            )}
            <ToastPrimitive.Close
              aria-label="Dismiss"
              className="cursor-pointer text-grey hover:text-navy"
            >
              ✕
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-50 flex w-96 max-w-[92vw] flex-col gap-2" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}
