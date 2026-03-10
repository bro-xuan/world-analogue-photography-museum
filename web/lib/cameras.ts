export interface CameraEntry {
  id: string;
  name: string;
  manufacturer: string;
  year: number | null;
  format: string | null;
  country?: string;
  tier: "xl" | "l" | "m";
  image: string;
}

export interface LandingData {
  meta: { total: number; generated_at: string };
  cameras: CameraEntry[];
}

export interface RelatedCamera {
  id: string;
  name: string;
  image?: string;
  year?: number;
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
  cameraType?: string;
  priceAdjusted?: number;
  relatedCameras?: RelatedCamera[];
}

export async function loadLandingData(): Promise<LandingData> {
  const fs = await import("fs/promises");
  const path = await import("path");
  const filePath = path.join(process.cwd(), "public", "data", "landing.json");
  const raw = await fs.readFile(filePath, "utf-8");
  return JSON.parse(raw);
}

export async function loadAllCameraDetails(): Promise<
  Record<string, CameraDetail>
> {
  const fs = await import("fs/promises");
  const path = await import("path");
  const filePath = path.join(
    process.cwd(),
    "public",
    "data",
    "cameras_detail.json"
  );
  const raw = await fs.readFile(filePath, "utf-8");
  return JSON.parse(raw);
}

export async function loadCameraDetail(
  id: string
): Promise<CameraDetail | null> {
  const all = await loadAllCameraDetails();
  return all[id] ?? null;
}
