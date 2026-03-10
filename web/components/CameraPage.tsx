"use client";

import { useState } from "react";
import Link from "next/link";
import { CameraDetail } from "@/lib/cameras";
import RelatedCameras from "@/components/camera/RelatedCameras";

const SPEC_LABELS: Record<string, string> = {
  format: "Film Format",
  lens: "Lens / Mount",
  shutter: "Shutter",
  metering: "Metering",
  weight: "Weight",
  dimensions: "Dimensions",
  battery: "Battery",
};

const RATING_LABELS: Record<string, string> = {
  buildQuality: "Build Quality",
  value: "Value",
  collectibility: "Collectibility",
  historicalSignificance: "Historical Significance",
};

export default function CameraPage({ camera }: { camera: CameraDetail }) {
  const [activeImage, setActiveImage] = useState(0);

  const yearDuration =
    camera.year && camera.yearEnd
      ? camera.yearEnd - camera.year
      : null;

  const yearText = camera.year
    ? camera.yearEnd
      ? `${camera.year}–${camera.yearEnd}${yearDuration && yearDuration > 0 ? ` (${yearDuration} years)` : ""}`
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
      {/* Breadcrumb nav */}
      <nav className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-neutral-100">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-2 text-sm">
          <Link
            href="/"
            className="text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            Museum
          </Link>
          <span className="text-neutral-200">/</span>
          <span className="text-neutral-400">{camera.manufacturer}</span>
          <span className="text-neutral-200">/</span>
          <span className="text-neutral-600 truncate">{camera.name}</span>
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

            {/* Camera type badge */}
            {camera.cameraType && (
              <span className="inline-block mt-2 px-3 py-1 text-xs font-medium text-neutral-500 bg-neutral-100 rounded-full">
                {camera.cameraType}
              </span>
            )}

            <p className={`${camera.cameraType ? "mt-2" : "mt-2"} text-sm text-neutral-400`}>
              {subtitle}
            </p>

            {camera.description && (
              <div className="mt-6 text-base text-neutral-700 leading-relaxed space-y-3">
                {camera.description.split("\n\n").map((para, i) => (
                  <p key={i}>{para}</p>
                ))}
              </div>
            )}

            {/* Specs table */}
            {camera.specs && Object.keys(camera.specs).length > 0 && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Specifications
                </h2>
                <table className="w-full text-sm">
                  <tbody>
                    {Object.entries(camera.specs).map(([key, value], i) => (
                      <tr
                        key={key}
                        className={i % 2 === 0 ? "bg-neutral-50" : ""}
                      >
                        <td className="px-3 py-2 text-neutral-400 font-medium w-1/3">
                          {SPEC_LABELS[key] || key}
                        </td>
                        <td className="px-3 py-2 text-neutral-700">
                          {value}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pricing */}
            {(camera.priceLaunch || camera.priceMarket) && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Pricing
                </h2>
                <div className="grid grid-cols-2 gap-2">
                  {camera.priceLaunch != null && (
                    <div className="bg-neutral-50 rounded-lg px-3 py-2.5">
                      <dt className="text-[11px] text-neutral-400 uppercase tracking-wide">
                        Launch Price
                      </dt>
                      <dd className="text-sm text-neutral-700 mt-0.5">
                        ${camera.priceLaunch.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                        {camera.year ? ` (${camera.year})` : ""}
                      </dd>
                      {camera.priceAdjusted != null && (
                        <dd className="text-xs text-neutral-400 mt-1">
                          ≈ ${camera.priceAdjusted.toLocaleString("en-US")} in 2024 dollars
                        </dd>
                      )}
                    </div>
                  )}
                  {camera.priceMarket != null && (
                    <div className="bg-neutral-50 rounded-lg px-3 py-2.5">
                      <dt className="text-[11px] text-neutral-400 uppercase tracking-wide">
                        Market Value
                      </dt>
                      <dd className="text-sm text-neutral-700 mt-0.5">
                        ~${camera.priceMarket.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </dd>
                    </div>
                  )}
                </div>
              </div>
            )}
            {/* Ratings */}
            {camera.ratings && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Editorial Ratings
                </h2>
                <div className="space-y-2.5">
                  {Object.entries(camera.ratings).map(([key, score]) => (
                    <div key={key}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-neutral-600">
                          {RATING_LABELS[key] || key}
                        </span>
                        <span className="text-sm font-medium text-neutral-700">
                          {score.toFixed(1)}
                        </span>
                      </div>
                      <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-neutral-700 rounded-full transition-all"
                          style={{ width: `${(score / 5) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Related cameras */}
        {camera.relatedCameras && camera.relatedCameras.length > 0 && (
          <RelatedCameras
            cameras={camera.relatedCameras}
            manufacturer={camera.manufacturer}
          />
        )}
      </main>
    </div>
  );
}
