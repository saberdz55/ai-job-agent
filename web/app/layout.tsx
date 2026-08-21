import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Job Agent",
  description: "Durable job discovery and application control plane",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#0b0d10", color: "#f5f7fa" }}>
        {children}
      </body>
    </html>
  );
}
