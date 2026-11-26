import { Navigate, type RouteObject } from "react-router";

import { OpsShell } from "./OpsShell";
import { AddPersonView } from "./views/AddPersonView";
import { AnnouncementsView } from "./views/AnnouncementsView";
import { AnnouncementView } from "./views/AnnouncementView";
import { ComposeAnnouncementView } from "./views/ComposeAnnouncementView";
import { CohortsView } from "./views/CohortsView";
import { OrganisationsView } from "./views/OrganisationsView";
import { PeopleView } from "./views/PeopleView";
import { CohortQuotaView, OrganisationQuotaView, PersonQuotaView } from "./views/QuotaView";
import { RequestsView } from "./views/RequestsView";

/** The ops pages' routes (ops-pages-copy.md § Addresses and shell). */
export const opsRoutes: RouteObject[] = [
  {
    path: "/",
    element: <OpsShell />,
    children: [
      { index: true, element: <Navigate to="/people" replace /> },
      { path: "people", element: <PeopleView /> },
      { path: "people/new", element: <AddPersonView /> },
      { path: "people/:userId/quota", element: <PersonQuotaView /> },
      { path: "organisations", element: <OrganisationsView /> },
      { path: "organisations/:orgId/quota", element: <OrganisationQuotaView /> },
      { path: "cohorts", element: <CohortsView /> },
      { path: "cohorts/:cohortId/quota", element: <CohortQuotaView /> },
      { path: "announcements", element: <AnnouncementsView /> },
      { path: "announcements/new", element: <ComposeAnnouncementView /> },
      { path: "announcements/:announcementId", element: <AnnouncementView /> },
      { path: "waitlist", element: <RequestsView /> },
      { path: "*", element: <Navigate to="/people" replace /> },
    ],
  },
];
