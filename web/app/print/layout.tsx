// Printable documents: no app shell, just the page on paper.
export default function PrintLayout({ children }: LayoutProps<"/print">) {
  return <div className="min-h-dvh bg-surface text-ink">{children}</div>;
}
