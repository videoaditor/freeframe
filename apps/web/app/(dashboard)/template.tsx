/**
 * A template (unlike a layout) remounts on every navigation, so each screen enters with the same
 * short rise-and-unblur instead of snapping in. The sidebar and header live in the layout and stay
 * perfectly still - only the content moves, which is what makes it read as one app.
 */
export default function DashboardTemplate({ children }: { children: React.ReactNode }) {
  return <div className="route-in h-full">{children}</div>
}
