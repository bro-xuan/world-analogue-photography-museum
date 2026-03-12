import { notFound } from "next/navigation";
import { loadBrandsData } from "@/lib/brands.server";
import BrandPage from "@/components/BrandPage";

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  const data = await loadBrandsData();
  return data.allBrands.map((b) => ({ slug: b.slug }));
}

export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  const data = await loadBrandsData();
  const brand = data.allBrands.find((b) => b.slug === slug);
  if (!brand) return { title: "Brand Not Found" };
  const title = `${brand.name} — World Analogue Photography Museum`;
  const description = `Browse ${brand.cameraCount} analogue cameras by ${brand.name}.`;
  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { card: "summary_large_image" as const },
  };
}

export default async function BrandDetailPage({ params }: Props) {
  const { slug } = await params;
  const data = await loadBrandsData();
  const brand = data.allBrands.find((b) => b.slug === slug);
  if (!brand) notFound();
  return <BrandPage brand={brand} />;
}
