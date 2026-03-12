import BrandsListing from "@/components/BrandsListing";

export const metadata = {
  title: "Camera Brands — World Analog Photography Museum",
  description: "Browse analog camera brands from around the world.",
  openGraph: {
    title: "Camera Brands — World Analog Photography Museum",
    description: "Browse analog camera brands from around the world.",
    type: "website",
    siteName: "World Analog Photography Museum",
  },
  twitter: { card: "summary_large_image" as const },
};

export default function BrandsPage() {
  return <BrandsListing />;
}
