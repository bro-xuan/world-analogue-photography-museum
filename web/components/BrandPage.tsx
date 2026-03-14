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

  const pagePad = "max(24px, 2.2vw)";

  return (
    <div className="min-h-screen bg-white">
      <main style={{ padding: `max(32px, 3vh) ${pagePad} max(64px, 6vh)` }}>
        {/* Breadcrumb */}
        <div
          className="flex items-center"
          style={{ gap: "max(6px, 0.6vh)", fontSize: "max(14px, 1.3vh)", marginBottom: "max(24px, 2.2vh)" }}
        >
          <Link href="/brands" className="text-neutral-400 hover:text-neutral-900 transition-colors">
            Brands
          </Link>
          <span className="text-neutral-300">/</span>
          <span className="text-neutral-600 truncate">{brand.name}</span>
        </div>
        {/* Brand header */}
        <div>
          {brand.logo && (
            <div style={{ height: "max(56px, 5.5vh)", marginBottom: "max(16px, 1.5vh)" }}>
              <img
                src={`/${brand.logo}`}
                alt={brand.name}
                className="max-h-full object-contain"
                style={{ maxWidth: "max(200px, 18vh)" }}
              />
            </div>
          )}
          <h1
            className="font-display font-bold text-neutral-900 leading-tight"
            style={{ fontSize: "max(32px, 3.2vh)" }}
          >
            {brand.name}
          </h1>
          <p className="text-neutral-400" style={{ marginTop: "max(8px, 0.7vh)", fontSize: "max(15px, 1.4vh)" }}>
            {brand.country && <>{brand.country} &middot; </>}
            {brand.cameraCount} camera{brand.cameraCount !== 1 ? "s" : ""}
            {yearRange && <> &middot; {yearRange}</>}
          </p>
        </div>

        {/* Camera grid grouped by decade */}
        <div style={{ marginTop: "max(32px, 3vh)" }}>
          {decades.map(([decade, cameras]) => (
            <section key={decade} style={{ marginBottom: "max(32px, 3vh)" }}>
              <h2
                className="font-semibold text-neutral-400 uppercase"
                style={{ fontSize: "max(13px, 1.2vh)", letterSpacing: "0.05em", marginBottom: "max(14px, 1.3vh)" }}
              >
                {decade}
              </h2>
              <div
                className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6"
                style={{
                  gap: "max(8px, 1.5vh)",
                }}
              >
                {cameras.map((cam) => (
                  <CameraTile
                    key={cam.id}
                    camera={cam as CameraEntry}
                    browse
                  />
                ))}
              </div>
            </section>
          ))}
        </div>

        {hasMore && (
          <div className="flex justify-center" style={{ paddingBottom: "max(32px, 3vh)" }}>
            <button
              onClick={loadMore}
              className="font-medium text-neutral-700 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer"
              style={{ padding: "max(8px, 0.75vh) max(24px, 2.2vh)", fontSize: "max(14px, 1.3vh)" }}
            >
              Load more ({brand.cameras.length - visibleCount} remaining)
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
