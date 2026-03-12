"use client";

import { useState, useMemo, useEffect } from "react";
import { BrandsData } from "@/lib/brands";
import { fetchBrandsData } from "@/lib/brands";
import BrandTile from "./BrandTile";

export default function BrandsListing() {
  const [data, setData] = useState<BrandsData | null>(null);
  const [search, setSearch] = useState("");
  const [activeRegion, setActiveRegion] = useState<string | null>(null);

  useEffect(() => {
    fetchBrandsData().then(setData).catch(console.error);
  }, []);

  const visibleBrands = useMemo(() => {
    if (!data) return [];
    let brands = data.allBrands;

    if (activeRegion) {
      const region = data.regions.find((r) => r.name === activeRegion);
      if (!region) return [];
      brands = region.brands;
    }

    if (search) {
      const q = search.toLowerCase();
      brands = brands.filter((b) => b.name.toLowerCase().includes(q));
    }

    return brands;
  }, [data, search, activeRegion]);

  if (!data) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-900 rounded-full animate-spin" />
      </div>
    );
  }

  const fs = {
    title: "max(36px, 3.8vh)",
    subtitle: "max(16px, 1.5vh)",
    label: "max(12px, 1.15vh)",
    pill: "max(14px, 1.35vh)",
    pillPad: "max(6px, 0.55vh) max(16px, 1.5vh)",
    search: "max(15px, 1.4vh)",
    pagePad: "max(24px, 2.2vw)",
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <div style={{ padding: `max(40px, 4vh) ${fs.pagePad} max(16px, 1.5vh)` }}>
        <h1
          className="font-display font-bold text-neutral-900 leading-tight"
          style={{ fontSize: fs.title }}
        >
          Camera Brands
        </h1>
        <p className="text-neutral-400" style={{ fontSize: fs.subtitle, marginTop: "max(4px, 0.4vh)" }}>
          {data.meta.total} manufacturers
        </p>
      </div>

      {/* Filters */}
      <div className="border-b border-neutral-100" style={{ padding: `0 ${fs.pagePad} max(20px, 1.8vh)` }}>
        <div className="flex flex-wrap" style={{ gap: "max(8px, 0.7vh)", marginBottom: "max(14px, 1.3vh)" }}>
          <button
            onClick={() => setActiveRegion(null)}
            className={`rounded-full border transition-colors cursor-pointer ${
              activeRegion === null
                ? "bg-neutral-900 text-white border-neutral-900"
                : "text-neutral-500 border-neutral-200 hover:border-neutral-400"
            }`}
            style={{ padding: fs.pillPad, fontSize: fs.pill }}
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
              className={`rounded-full border transition-colors cursor-pointer ${
                activeRegion === region.name
                  ? "bg-neutral-900 text-white border-neutral-900"
                  : "text-neutral-500 border-neutral-200 hover:border-neutral-400"
              }`}
              style={{ padding: fs.pillPad, fontSize: fs.pill }}
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

        <div className="relative" style={{ maxWidth: "max(360px, 30vw)" }}>
          <svg
            className="absolute top-1/2 -translate-y-1/2 text-neutral-300"
            style={{ left: "max(12px, 1.1vh)", width: "max(16px, 1.5vh)", height: "max(16px, 1.5vh)" }}
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
            className="w-full border border-neutral-200 rounded-lg outline-none focus:border-neutral-400 transition-colors"
            style={{
              paddingLeft: "max(36px, 3.4vh)",
              paddingRight: "max(16px, 1.5vh)",
              paddingTop: "max(8px, 0.75vh)",
              paddingBottom: "max(8px, 0.75vh)",
              fontSize: fs.search,
            }}
          />
        </div>
      </div>

      {/* Brand grid */}
      <main style={{ padding: `max(32px, 3vh) ${fs.pagePad} max(64px, 6vh)` }}>
        {visibleBrands.length === 0 ? (
          <p className="text-neutral-400 text-center" style={{ padding: "max(64px, 6vh) 0", fontSize: fs.subtitle }}>
            No brands match your search
          </p>
        ) : (
          <div
            className="grid"
            style={{
              gridTemplateColumns:
                "repeat(auto-fill, minmax(max(120px, 10vh), 1fr))",
              gap: "max(20px, 1.8vh) max(16px, 1.4vh)",
            }}
          >
            {visibleBrands.map((brand) => (
              <BrandTile key={brand.slug} brand={brand} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
