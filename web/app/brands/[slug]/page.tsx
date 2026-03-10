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
  return {
    title: `${brand.name} — World Analogue Photography Museum`,
    description: `Browse ${brand.cameraCount} analogue cameras by ${brand.name}.`,
  };
}

export default async function BrandDetailPage({ params }: Props) {
  const { slug } = await params;
  const data = await loadBrandsData();
  const brand = data.allBrands.find((b) => b.slug === slug);
  if (!brand) notFound();
  return <BrandPage brand={brand} />;
}
