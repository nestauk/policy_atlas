import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "../index.css";
import { OpsApp } from "./OpsApp";

async function bootstrap() {
  if (import.meta.env.VITE_MOCK === "1") {
    const { installOpsMock } = await import("./mock");
    installOpsMock();
  }
  const rootElement = document.getElementById("root");
  if (!rootElement) throw new Error("Root element #root not found");
  createRoot(rootElement).render(
    <StrictMode>
      <OpsApp />
    </StrictMode>,
  );
}

void bootstrap();
