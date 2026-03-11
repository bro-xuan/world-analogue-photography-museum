"use client";

import { useState, useMemo, useEffect } from "react";
import { BrandsData, BrandRegion } from "@/lib/brands";
import { fetchBrandsData } from "@/lib/brands";
import BrandTile from "./BrandTile";

export default function BrandsListing() {
  const [data, setData] = useState<BrandsData | null>(null);
  const [search, setSearch] = useState("");
  const [activeRegion, setActiveRegion] = useState<string | null>(null);

  useEffect(() => {
    fetchBrandsData().then(setData);
  }, []);

  const visibleRegions = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase();

    if (activeRegion) {
      const region = data.regions.find((r) => r.name === activeRegion);
      if (!region) return [];
      const brands = q
        ? region.brands.filter((b) => b.name.toLowerCase().includes(q))
        : region.brands;
      return brands.length > 0
        ? [{ ...region, brands, count: brands.length }]
        : [];
    }

    if (q) {
      const filtered = data.allBrands.filter((b) =>
        b.name.toLowerCase().includes(q)
      );
      return filtered.length > 0
        ? [{ name: "Results", count: filtered.length, brands: filtered }]
        : [];
    }

    return data.regions;
  }, [data, search, activeRegion]);

  if (!data) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-900 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div className="bg-neutral-50 border-b border-neutral-200">
        <div className="max-w-6xl mx-auto px-6 pt-10 pb-8">
          <p className="text-xs font-semibold tracking-widest text-neutral-400 uppercase mb-2">
            Archive
          </p>
          <h1 className="font-display text-4xl md:text-5xl font-bold text-neutral-900">
            Camera Brands
          </h1>
          <p className="mt-1 text-lg text-neutral-400">
            {data.meta.total} manufacturers
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="border-b border-neutral-200">
        <div className="max-w-6xl mx-auto px-6 py-4 space-y-3">
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setActiveRegion(null)}
              className={`px-3.5 py-1.5 text-sm rounded-full border transition-colors cursor-pointer ${
                activeRegion === null
                  ? "bg-neutral-900 text-white border-neutral-900"
                  : "text-neutral-500 border-neutral-200 hover:border-neutral-400"
              }`}
            >
              All{" "}
              <span className={activeRegion === null ? "text-neutral-400" : "text-neutral-300"}>
                {data.meta.total}
              </span>
            </button>
            {data.regions.map((region) => (
              <button
                key={region.name}
                onClick={() =>
                  setActiveRegion(
                    activeRegion === region.name ? null : region.name
                  )
                }
                className={`px-3.5 py-1.5 text-sm rounded-full border transition-colors cursor-pointer ${
                  activeRegion === region.name
                    ? "bg-neutral-900 text-white border-neutral-900"
                    : "text-neutral-500 border-neutral-200 hover:border-neutral-400"
                }`}
              >
                {region.name}{" "}
                <span
                  className={
                    activeRegion === region.name
                      ? "text-neutral-400"
                      : "text-neutral-300"
                  }
                >
                  {region.count}
                </span>
              </button>
            ))}
          </div>

          <div className="relative max-w-sm">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <circle cx="11" cy="11" r="8" strokeWidth="2" />
              <path d="m21 21-4.35-4.35" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              placeholder="Search brands..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-sm border border-neutral-200 rounded-lg outline-none focus:border-neutral-400 transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Brand grid */}
      <main className="max-w-6xl mx-auto px-6 pt-8 pb-16">
        {visibleRegions.length === 0 ? (
          <p className="text-neutral-400 text-center py-16">
            No brands match your search
          </p>
        ) : (
          visibleRegions.map((region) => (
            <section key={region.name} className="mb-12">
              <div className="flex items-baseline gap-3 mb-5">
                <h2 className="text-lg font-semibold text-neutral-900">
                  {region.name}
                </h2>
                <span className="text-sm text-neutral-300">
                  {region.count}
                </span>
              </div>
              <div
                className="grid gap-x-4 gap-y-6"
                style={{
                  gridTemplateColumns:
                    "repeat(auto-fill, minmax(140px, 1fr))",
                }}
              >
                {region.brands.map((brand) => (
                  <BrandTile key={brand.slug} brand={brand} />
                ))}
              </div>
            </section>
          ))
        )}
      </main>
    </div>
  );
}
