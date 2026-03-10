import fs from "fs/promises";
import path from "path";
import type { BrandsData } from "./brands";

let _cache: BrandsData | null = null;

export async function loadBrandsData(): Promise<BrandsData> {
  if (_cache) return _cache;
  const filePath = path.join(process.cwd(), "public", "data", "brands.json");
  const raw = await fs.readFile(filePath, "utf-8");
  _cache = JSON.parse(raw);
  return _cache!;
}
