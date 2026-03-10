"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { BrandEntry, BrandCamera } from "@/lib/brands";
import { CameraEntry } from "@/lib/cameras";
import CameraTile from "./CameraTile";

const PAGE_SIZE = 100;

function groupByDecade(cameras: BrandCamera[]): [string, BrandCamera[]][] {
  const groups = new Map<string, BrandCamera[]>();
  const noYear: BrandCamera[] = [];

  for (const cam of cameras) {
    if (cam.year) {
      const decade = `${Math.floor(cam.year / 10) * 10}s`;
      if (!groups.has(decade)) groups.set(decade, []);
      groups.get(decade)!.push(cam);
    } else {
      noYear.push(cam);
    }
  }

  const result: [string, BrandCamera[]][] = Array.from(groups.entries()).sort(
    (a, b) => a[0].localeCompare(b[0])
  );
  if (noYear.length > 0) {
    result.push(["Unknown year", noYear]);
  }
  return result;
}

export default function BrandPage({ brand }: { brand: BrandEntry }) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const loadMore = useCallback(() => {
    setVisibleCount((prev) => Math.min(prev + PAGE_SIZE, brand.cameras.length));
  }, [brand.cameras.length]);

  const visibleCameras = brand.cameras.slice(0, visibleCount);
  const hasMore = visibleCount < brand.cameras.length;
  const decades = groupByDecade(visibleCameras);

  const yearRange =
    brand.yearStart && brand.yearEnd
      ? brand.yearStart === brand.yearEnd
        ? `${brand.yearStart}`
        : `${brand.yearStart}–${brand.yearEnd}`
      : brand.yearStart
        ? `${brand.yearStart}`
        : null;

  return (
    <div className="min-h-screen bg-white">
      {/* Breadcrumb */}
      <nav className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-neutral-100">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-1.5 text-sm">
          <Link
            href="/"
            className="text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            Museum
          </Link>
          <span className="text-neutral-300">/</span>
          <Link
            href="/brands"
            className="text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            Brands
          </Link>
          <span className="text-neutral-300">/</span>
          <span className="text-neutral-600 truncate">{brand.name}</span>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 pt-10 pb-16">
        {/* Brand header */}
        <div>
          <h1 className="font-display text-3xl md:text-4xl font-bold text-neutral-900">
            {brand.name}
          </h1>
          <p className="mt-2 text-sm text-neutral-400">
            {brand.country && <>{brand.country} &middot; </>}
            {brand.cameraCount} camera{brand.cameraCount !== 1 ? "s" : ""}
            {yearRange && <> &middot; {yearRange}</>}
          </p>
        </div>

        {/* Camera grid grouped by decade */}
        <div className="mt-8">
          {decades.map(([decade, cameras]) => (
            <section key={decade} className="mb-8">
              <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                {decade}
              </h2>
              <div
                className="grid gap-4"
                style={{
                  gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                }}
              >
                {cameras.map((cam) => (
                  <CameraTile
                    key={cam.id}
                    camera={cam as CameraEntry}
                    hasDetail={!!cam.hasDetail}
                    browse
                  />
                ))}
              </div>
            </section>
          ))}
        </div>

        {hasMore && (
          <div className="flex justify-center pb-8">
            <button
              onClick={loadMore}
              className="px-6 py-2 text-sm font-medium text-neutral-700 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer"
            >
              Load more ({brand.cameras.length - visibleCount} remaining)
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
