import type { Metadata, Viewport } from "next";
import { ToastProvider } from "@/components/shared/toast";
import { ThemeInitializer } from "@/components/shared/theme-initializer";
import "./globals.css";

// SF Pro via the system font stack (--font-sans in globals.css), per the Aditor guidelines and
// Apple's HIG: native type, no download, Dynamic Type friendly.
export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: "Autoreview",
  icons: { icon: "/autoreview-check-v2.png", apple: "/apple-icon.png" },
  description: "Request files, get instant feedback. Like WeTransfer, with a reviewer built in.",
  // Generic branding only: link crawlers must not receive private review content.
  openGraph: {
    type: "website",
    siteName: "AutoReview",
    title: "AutoReview",
    description: "Request files, get instant feedback.",
    images: [{ url: "/autoreview-check-v2.png", width: 512, height: 512, alt: "AutoReview blue check" }],
  },
  twitter: {
    card: "summary",
    title: "AutoReview",
    description: "Request files, get instant feedback.",
    images: [{ url: "/autoreview-check-v2.png", alt: "AutoReview blue check" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0A0A0B",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Inline script to apply theme BEFORE paint — prevents flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var d=JSON.parse(localStorage.getItem('ff-theme')||'{}');var t=d.state&&d.state.theme||'dark';if(t==='system'){t=window.matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'}document.documentElement.setAttribute('data-theme',t)}catch(e){document.documentElement.setAttribute('data-theme','dark')}})()`,
          }}
        />
        {/* Page-view analytics (self-hosted Umami). Long token-like path segments (share/invite links)
            are replaced with ":id" before sending, and query strings/hashes are never sent. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `window.umamiScrub=function(t,p){var s=function(u){return u&&u.replace(/\\/[A-Za-z0-9_-]{20,}(?=[\\/?#]|$)/g,'/:id')};p.url=s(p.url);p.referrer=s(p.referrer);return p}`,
          }}
        />
        <script
          defer
          src="https://metrics.aditor.ai/script.js"
          data-website-id="48ef0aa8-5e02-4c88-b437-0edc2e9463ac"
          data-exclude-search="true"
          data-exclude-hash="true"
          data-before-send="umamiScrub"
        />
      </head>
      <body className="font-sans antialiased">
        <ThemeInitializer />
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
