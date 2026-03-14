export interface CameraEntry {
  id: string;
  name: string;
  manufacturer: string;
  year: number | null;
  format: string | null;
  country?: string;
  image: string;
  color?: string;
}

export function thumbUrl(camera: CameraEntry): string {
  return camera.image.replace(/\/[^/]+$/, "/thumb.webp");
}

export interface LandingData {
  meta: { total: number; generated_at: string };
  cameras: CameraEntry[];
}

/** Client-side fetch for landing data (used in browser) */
export async function fetchLandingData(): Promise<LandingData> {
  const res = await fetch("/data/landing.json");
  return res.json();
}

export interface RelatedCamera {
  id: string;
  name: string;
  image?: string;
  year?: number;
}

export interface CameraRatings {
  buildQuality: number;
  value: number;
  collectibility: number;
  historicalSignificance: number;
}

export interface CameraDetail {
  name: string;
  manufacturer: string;
  country?: string;
  description?: string;
  year?: number;
  yearEnd?: number;
  images: string[];
  specs?: Record<string, string>;
  priceLaunch?: number;
  priceMarket?: number;
  priceLaunchSource?: string;
  priceMarketSource?: string;
  priceAdjusted?: number;
  relatedCameras?: RelatedCamera[];
  ratings?: CameraRatings;
}
