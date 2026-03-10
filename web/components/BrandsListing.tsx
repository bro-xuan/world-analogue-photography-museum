"use client";

import { useState, useMemo, useEffect } from "react";
import Link from "next/link";
import { BrandsData } from "@/lib/brands";
import { fetchBrandsData } from "@/lib/brands";
import BrandTile from "./BrandTile";

export default function BrandsListing() {
  const [data, setData] = useState<BrandsData | null>(null);
  const [search, setSearch] = useState("");
  const [activeRegion, setActiveRegion] = useState<string | null>(null);

  useEffect(() => {
    fetchBrandsData().then(setData);
  }, []);

  const filteredBrands = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase();
    let brands = data.allBrands;
    if (activeRegion) {
      brands = brands.filter((b) => b.region === activeRegion);
    }
    if (q) {
      brands = brands.filter((b) => b.name.toLowerCase().includes(q));
    }
    return brands;
  }, [data, search, activeRegion]);

  const showGrouped = !search && !activeRegion;

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
      <nav className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-neutral-100">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-1.5 text-sm">
          <Link
            href="/"
            className="text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            Museum
          </Link>
          <span className="text-neutral-300">/</span>
          <span className="text-neutral-600">Brands</span>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 pt-8 pb-16">
        {/* Title */}
        <div className="flex items-baseline gap-3 flex-wrap">
          <h1 className="font-display text-3xl md:text-4xl font-bold text-neutral-900">
            Camera Brands
          </h1>
          <span className="text-sm text-neutral-400">
            {data.meta.total} brands
          </span>
        </div>

        {/* Search + Region filters */}
        <div className="mt-6 space-y-3">
          <input
            type="text"
            placeholder="Search brands..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full max-w-sm px-4 py-2 text-sm border border-neutral-200 rounded-full outline-none focus:border-neutral-400 transition-colors"
          />

          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setActiveRegion(null)}
              className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors cursor-pointer ${
                activeRegion === null
                  ? "bg-neutral-900 text-white border-neutral-900"
                  : "text-neutral-500 border-neutral-200 hover:border-neutral-400"
              }`}
            >
              All
            </button>
            {data.regions.map((region) => (
              <button
                key={region.name}
                onClick={() =>
                  setActiveRegion(
                    activeRegion === region.name ? null : region.name
                  )
                }
                className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors cursor-pointer ${
                  activeRegion === region.name
                    ? "bg-neutral-900 text-white border-neutral-900"
                    : "text-neutral-500 border-neutral-200 hover:border-neutral-400"
                }`}
              >
                {region.name}{" "}
                <span className="opacity-60">{region.count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Brand grid */}
        <div className="mt-8">
          {showGrouped ? (
            // Grouped by region
            data.regions.map((region) => (
              <section key={region.name} className="mb-10">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">
                  {region.name}{" "}
                  <span className="font-normal">({region.count})</span>
                </h2>
                <div
                  className="grid gap-4"
                  style={{
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(180px, 1fr))",
                  }}
                >
                  {region.brands.map((brand) => (
                    <BrandTile key={brand.slug} brand={brand} />
                  ))}
                </div>
              </section>
            ))
          ) : (
            // Flat filtered list
            <>
              {filteredBrands.length === 0 ? (
                <p className="text-neutral-400 text-center py-16">
                  No brands match your search
                </p>
              ) : (
                <div
                  className="grid gap-4"
                  style={{
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(180px, 1fr))",
                  }}
                >
                  {filteredBrands.map((brand) => (
                    <BrandTile key={brand.slug} brand={brand} />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
