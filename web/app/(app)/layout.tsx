import { Shell } from "@/components/shell";
import { SessionProvider } from "@/lib/session";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <SessionProvider>
      <Shell>{children}</Shell>
    </SessionProvider>
  );
}
