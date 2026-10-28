import View from "./view";

// Every screen renders after the session and its data load, so there is no static shell for Next to check for instant navigation.
export const instant = false;

export default function Page() {
  return <View />;
}
