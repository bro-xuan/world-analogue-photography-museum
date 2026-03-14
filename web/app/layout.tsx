import type { Metadata } from "next";
import { Inter, Playfair_Display, Space_Mono } from "next/font/google";
import "./globals.css";
import Providers from "@/components/Providers";
import NavBar from "@/components/NavBar";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
});

const spaceMono = Space_Mono({
  variable: "--font-space-mono",
  subsets: ["latin"],
  weight: ["700"],
});

export const metadata: Metadata = {
  title: "World Analog Photography Museum",
  description:
    "A living museum of every analog camera and film ever made. Browse thousands of cameras from hundreds of manufacturers.",
  openGraph: {
    type: "website",
    title: "World Analog Photography Museum",
    description:
      "A living museum of every analog camera and film ever made. Browse thousands of cameras from hundreds of manufacturers.",
    siteName: "World Analog Photography Museum",
  },
  twitter: { card: "summary_large_image" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preload" href="/data/landing.json" as="fetch" crossOrigin="anonymous" />
      </head>
      <body
        className={`${inter.variable} ${playfair.variable} ${spaceMono.variable} antialiased bg-white`}
      >
        <Providers>
          <NavBar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
