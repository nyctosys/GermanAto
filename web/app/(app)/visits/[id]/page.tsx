import VisitPage from "./visit-page";

// The screen renders only after the session and the visit load, so there is no static shell to validate for instant navigation.
export const instant = false;

export default function Page() {
  return <VisitPage />;
}
