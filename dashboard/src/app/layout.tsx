import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Gateway Dashboard",
  description: "Cost monitoring and usage analytics for the AI Gateway",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-gray-950 text-gray-100 antialiased min-h-screen">
        <div className="flex min-h-screen">
          <nav className="w-56 bg-gray-900 border-r border-gray-800 p-4 flex flex-col gap-1">
            <div className="text-lg font-bold text-white mb-6 px-2">
              AI Gateway
            </div>
            <a
              href="/"
              className="px-3 py-2 rounded-md text-sm hover:bg-gray-800 text-gray-300 hover:text-white transition"
            >
              Overview
            </a>
            <a
              href="/usage"
              className="px-3 py-2 rounded-md text-sm hover:bg-gray-800 text-gray-300 hover:text-white transition"
            >
              Usage & Costs
            </a>
            <a
              href="/teams"
              className="px-3 py-2 rounded-md text-sm hover:bg-gray-800 text-gray-300 hover:text-white transition"
            >
              Teams
            </a>
            <a
              href="/policies"
              className="px-3 py-2 rounded-md text-sm hover:bg-gray-800 text-gray-300 hover:text-white transition"
            >
              Policies
            </a>
          </nav>
          <main className="flex-1 p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
