import fs from "fs/promises";
import path from "path";
import type { LandingData, CameraDetail } from "./cameras";

export async function loadLandingData(): Promise<LandingData> {
  const filePath = path.join(process.cwd(), "public", "data", "landing.json");
  const raw = await fs.readFile(filePath, "utf-8");
  return JSON.parse(raw);
}

let _detailCache: Record<string, CameraDetail> | null = null;

export async function loadAllCameraDetails(): Promise<
  Record<string, CameraDetail>
> {
  if (_detailCache) return _detailCache;
  const filePath = path.join(
    process.cwd(),
    "public",
    "data",
    "cameras_detail.json"
  );
  const raw = await fs.readFile(filePath, "utf-8");
  _detailCache = JSON.parse(raw);
  return _detailCache!;
}

export async function loadCameraDetail(
  id: string
): Promise<CameraDetail | null> {
  const all = await loadAllCameraDetails();
  return all[id] ?? null;
}
