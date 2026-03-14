export interface BrandCamera {
  id: string;
  name: string;
  manufacturer: string;
  year?: number;
  format?: string;
  country?: string;
  image: string;
}

export interface BrandEntry {
  slug: string;
  name: string;
  country: string;
  region: string;
  cameraCount: number;
  heroImage: string;
  logo?: string;
  yearStart?: number;
  yearEnd?: number;
  cameras: BrandCamera[];
}

export interface BrandRegion {
  name: string;
  count: number;
  brands: BrandEntry[];
}

export interface BrandsData {
  meta: { total: number; generated_at: string };
  regions: BrandRegion[];
  allBrands: BrandEntry[];
}

/** Client-side fetch for brands data */
export async function fetchBrandsData(): Promise<BrandsData> {
  const res = await fetch("/data/brands.json");
  return res.json();
}
