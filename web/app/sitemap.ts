import type { MetadataRoute } from "next";
import { loadBrandsData } from "@/lib/brands.server";
import { loadAllCameraDetails } from "@/lib/cameras.server";

export const dynamic = "force-dynamic";

const BASE = "https://analogcams.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [brandsData, cameraDetails] = await Promise.all([
    loadBrandsData(),
    loadAllCameraDetails(),
  ]);

  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE, changeFrequency: "weekly", priority: 1.0 },
    { url: `${BASE}/brands`, changeFrequency: "weekly", priority: 0.9 },
  ];

  const brandPages: MetadataRoute.Sitemap = brandsData.allBrands.map(
    (brand) => ({
      url: `${BASE}/brands/${brand.slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })
  );

  const cameraPages: MetadataRoute.Sitemap = Object.keys(cameraDetails).map(
    (id) => ({
      url: `${BASE}/cameras/${id}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })
  );

  return [...staticPages, ...brandPages, ...cameraPages];
}
