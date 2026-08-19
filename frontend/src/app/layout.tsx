import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project Jatayu — Mission Control",
  description: "Drone-based plant disease detection mission control dashboard",
};
// Project Jataya
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
