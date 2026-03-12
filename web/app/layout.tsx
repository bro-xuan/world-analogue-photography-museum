import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
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

export const metadata: Metadata = {
  title: "World Analogue Photography Museum",
  description:
    "A living museum of every analogue camera and film ever made. Browse thousands of cameras from hundreds of manufacturers.",
  openGraph: {
    type: "website",
    title: "World Analogue Photography Museum",
    description:
      "A living museum of every analogue camera and film ever made. Browse thousands of cameras from hundreds of manufacturers.",
    siteName: "World Analogue Photography Museum",
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
      <body
        className={`${inter.variable} ${playfair.variable} antialiased bg-white`}
      >
        <Providers>
          <NavBar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
