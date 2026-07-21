import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentPropsWithoutRef } from "react";

import { cn } from "../brand/cn";

/*
 * Tabs (Radix copy-in) — workspace view switching. Active tab takes the
 * growing-underline language, matching the nav (one vocabulary).
 */

export const Tabs = TabsPrimitive.Root;
export const TabsContent = TabsPrimitive.Content;

export function TabsList({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("flex items-center gap-5 border-b border-line", className)}
      {...props}
    />
  );
}

export function TabsTrigger({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "-mb-px cursor-pointer border-b-2 border-transparent pb-2 text-[13px] font-semibold text-grey",
        "hover:text-navy focus-visible:outline-2 focus-visible:outline-blue",
        "data-[state=active]:border-blue data-[state=active]:font-extrabold data-[state=active]:text-navy",
        className,
      )}
      {...props}
    />
  );
}
