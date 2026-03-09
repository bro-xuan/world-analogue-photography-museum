"use client";

import { useState } from "react";
import Link from "next/link";
import { CameraDetail } from "@/lib/cameras";

const SPEC_LABELS: Record<string, string> = {
  format: "Film Format",
  lens: "Lens / Mount",
  shutter: "Shutter",
  metering: "Metering",
  weight: "Weight",
  dimensions: "Dimensions",
};

export default function CameraPage({ camera }: { camera: CameraDetail }) {
  const [activeImage, setActiveImage] = useState(0);

  const yearText = camera.year
    ? camera.yearEnd
      ? `${camera.year}–${camera.yearEnd}`
      : `${camera.year}`
    : null;

  const subtitle = [
    camera.manufacturer,
    camera.country,
    yearText,
    camera.specs?.format ? `${camera.specs.format} film` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="min-h-screen bg-white">
      {/* Top bar */}
      <nav className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-neutral-100">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <Link
            href="/"
            className="text-sm text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            &larr; Back
          </Link>
          <span className="text-neutral-200">|</span>
          <span className="text-sm text-neutral-400 font-display">
            World Analogue Photography Museum
          </span>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
          {/* Image column */}
          <div>
            <div className="aspect-square bg-neutral-50 rounded-lg overflow-hidden flex items-center justify-center">
              <img
                src={`/images/${camera.images[activeImage]}`}
                alt={camera.name}
                className="max-w-full max-h-full object-contain"
              />
            </div>

            {/* Thumbnail strip */}
            {camera.images.length > 1 && (
              <div className="flex gap-2 mt-3">
                {camera.images.map((img, i) => (
                  <button
                    key={img}
                    onClick={() => setActiveImage(i)}
                    className={`w-16 h-16 rounded overflow-hidden border-2 transition-colors cursor-pointer ${
                      i === activeImage
                        ? "border-neutral-900"
                        : "border-neutral-200 hover:border-neutral-400"
                    }`}
                  >
                    <img
                      src={`/images/${img}`}
                      alt=""
                      className="w-full h-full object-contain bg-neutral-50"
                    />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Info column */}
          <div>
            <h1 className="font-display text-3xl md:text-4xl font-bold text-neutral-900 leading-tight">
              {camera.name}
            </h1>

            <p className="mt-2 text-sm text-neutral-400">{subtitle}</p>

            {camera.description && (
              <p className="mt-6 text-base text-neutral-700 leading-relaxed">
                {camera.description}
              </p>
            )}

            {/* Specs table */}
            {camera.specs && Object.keys(camera.specs).length > 0 && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Specifications
                </h2>
                <dl className="border-t border-neutral-100">
                  {Object.entries(camera.specs).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex border-b border-neutral-100 py-2.5"
                    >
                      <dt className="w-32 shrink-0 text-sm text-neutral-400">
                        {SPEC_LABELS[key] || key}
                      </dt>
                      <dd className="text-sm text-neutral-700">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}

            {/* Pricing */}
            {(camera.priceLaunch || camera.priceMarket) && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Pricing
                </h2>
                <dl className="border-t border-neutral-100">
                  {camera.priceLaunch != null && (
                    <div className="flex border-b border-neutral-100 py-2.5">
                      <dt className="w-32 shrink-0 text-sm text-neutral-400">
                        Launch Price
                      </dt>
                      <dd className="text-sm text-neutral-700">
                        ${camera.priceLaunch.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                        {camera.year ? ` (${camera.year})` : ""}
                      </dd>
                    </div>
                  )}
                  {camera.priceMarket != null && (
                    <div className="flex border-b border-neutral-100 py-2.5">
                      <dt className="w-32 shrink-0 text-sm text-neutral-400">
                        Market Value
                      </dt>
                      <dd className="text-sm text-neutral-700">
                        ~${camera.priceMarket.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            )}

            {/* Sources */}
            {camera.sources && camera.sources.length > 0 && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Sources
                </h2>
                <div className="flex flex-wrap gap-2">
                  {camera.sources.map((src) => (
                    <a
                      key={src.url}
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-neutral-400 border border-neutral-200 rounded-full px-3 py-1 hover:text-neutral-700 hover:border-neutral-400 transition-colors"
                    >
                      {src.name}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
