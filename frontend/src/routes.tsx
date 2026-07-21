import { createBrowserRouter } from "react-router";
import { LandingView } from "./views/LandingView";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingView />,
  },
]);
