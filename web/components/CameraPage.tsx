"use client";

import { useState } from "react";
import Link from "next/link";
import { CameraDetail } from "@/lib/cameras";
import RelatedCameras from "@/components/camera/RelatedCameras";
import CollectionButtons from "@/components/camera/CollectionButtons";

const SPEC_LABELS: Record<string, string> = {
  format: "Film Format",
  lens: "Lens / Mount",
  shutter: "Shutter",
  metering: "Metering",
  weight: "Weight",
  dimensions: "Dimensions",
  battery: "Battery",
};

const PRICE_SOURCE_LABELS: Record<string, string> = {
  curated: "verified",
  llm: "est.",
  chinesecamera: "verified",
  ebay: "via eBay",
  collectiblend: "via Collectiblend",
};

const RATING_LABELS: Record<string, string> = {
  buildQuality: "Build Quality",
  value: "Value",
  collectibility: "Collectibility",
  historicalSignificance: "Historical Significance",
};

function RatingBar({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-neutral-500 w-40 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-neutral-800 rounded-full"
          style={{ width: `${(score / 5) * 100}%` }}
        />
      </div>
      <span className="text-sm font-medium text-neutral-700 w-8 text-right tabular-nums">
        {score.toFixed(1)}
      </span>
    </div>
  );
}

export default function CameraPage({ camera, cameraId }: { camera: CameraDetail; cameraId: string }) {
  const [activeImage, setActiveImage] = useState(0);
  const [failedImages, setFailedImages] = useState<Set<string>>(new Set());

  const validImages = camera.images.filter(img => !failedImages.has(img));
  const safeActive = Math.min(activeImage, Math.max(0, validImages.length - 1));

  const handleImageError = (img: string) => {
    setFailedImages(prev => new Set(prev).add(img));
  };

  const yearDuration =
    camera.year && camera.yearEnd
      ? camera.yearEnd - camera.year
      : null;

  const yearText = camera.year
    ? camera.yearEnd
      ? `${camera.year}–${camera.yearEnd}${yearDuration && yearDuration > 0 ? ` (${yearDuration} years)` : ""}`
      : `${camera.year}`
    : null;

  const metaParts = [
    camera.country,
    yearText,
    camera.specs?.format ? `${camera.specs.format} film` : null,
  ].filter(Boolean);

  const hasSpecs = camera.specs && Object.keys(camera.specs).length > 0;
  const hasPricing = camera.priceLaunch != null || camera.priceMarket != null;
  const hasRatings = camera.ratings && Object.keys(camera.ratings).length > 0;

  return (
    <div className="min-h-screen bg-white">
      <main className="max-w-6xl mx-auto px-6 pt-8 pb-16">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 text-sm mb-6">
          <Link
            href={`/brands/${camera.manufacturer.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`}
            className="text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            {camera.manufacturer}
          </Link>
          <span className="text-neutral-300">/</span>
          <span className="text-neutral-600 truncate">{camera.name}</span>
        </div>
        {/* Mobile: 4 grid items reordered via order. Desktop: 2-col with left sticky. */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr] lg:grid-cols-[5fr_6fr] gap-10 md:gap-14">
          {/* Image + thumbnails — order 1 on mobile, left column on desktop */}
          <div className="order-1 md:sticky md:top-20 md:self-start md:row-span-3">
            <div className="aspect-square bg-neutral-50 rounded-xl overflow-hidden flex items-center justify-center">
              {validImages.length > 0 ? (
                <img
                  src={`/images/${validImages[safeActive]}`}
                  alt={camera.name}
                  className="max-w-full max-h-full object-contain"
                  onError={() => handleImageError(validImages[safeActive])}
                />
              ) : (
                <div className="text-neutral-300 text-sm">No image available</div>
              )}
            </div>

            {/* Thumbnail strip */}
            {validImages.length > 1 && (
              <div className="flex gap-2 mt-3">
                {validImages.map((img, i) => (
                  <button
                    key={img}
                    onClick={() => setActiveImage(i)}
                    className={`w-14 h-14 rounded-lg overflow-hidden border-2 transition-colors cursor-pointer ${
                      i === safeActive
                        ? "border-neutral-900"
                        : "border-transparent hover:border-neutral-300"
                    }`}
                  >
                    <img
                      src={`/images/${img}`}
                      alt=""
                      className="w-full h-full object-contain bg-neutral-50"
                      onError={() => handleImageError(img)}
                    />
                  </button>
                ))}
              </div>
            )}

            {/* Pricing — under photo (desktop), reordered on mobile */}
            {hasPricing && (
              <div className="hidden md:block mt-6">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Pricing
                </h2>
                <div className="flex gap-3 flex-wrap">
                  {camera.priceMarket != null && (
                    <div className="px-4 py-2.5 bg-neutral-50 rounded-lg">
                      <div className="text-[11px] text-neutral-400 uppercase tracking-wide">
                        Market Value
                      </div>
                      <div className="text-lg font-semibold text-neutral-800 mt-0.5">
                        ~${camera.priceMarket.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </div>
                      {camera.priceMarketSource && (
                        <div className="text-[10px] text-neutral-400 mt-0.5">
                          {PRICE_SOURCE_LABELS[camera.priceMarketSource] || camera.priceMarketSource}
                        </div>
                      )}
                    </div>
                  )}
                  {camera.priceLaunch != null && (
                    <div className="px-4 py-2.5 bg-neutral-50 rounded-lg">
                      <div className="text-[11px] text-neutral-400 uppercase tracking-wide">
                        Launch Price{camera.year ? ` (${camera.year})` : ""}
                      </div>
                      <div className="text-lg font-semibold text-neutral-800 mt-0.5">
                        ${camera.priceLaunch.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </div>
                      {camera.priceAdjusted != null && (
                        <div className="text-xs text-neutral-400 mt-0.5">
                          ≈ ${camera.priceAdjusted.toLocaleString("en-US")} today
                        </div>
                      )}
                      {camera.priceLaunchSource && (
                        <div className="text-[10px] text-neutral-400 mt-0.5">
                          {PRICE_SOURCE_LABELS[camera.priceLaunchSource] || camera.priceLaunchSource}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right column: name → description → specs — order 2 on mobile */}
          <div className="order-2">
            {/* Header */}
            <div>
              <div className="flex items-start gap-3 flex-wrap">
                <h1 className="font-display text-3xl md:text-4xl font-bold text-neutral-900 leading-tight">
                  {camera.name}
                </h1>
                {camera.cameraType && (
                  <span className="mt-1.5 md:mt-2.5 inline-block px-2.5 py-0.5 text-xs font-medium text-neutral-500 bg-neutral-100 rounded-full whitespace-nowrap">
                    {camera.cameraType}
                  </span>
                )}
              </div>

              <p className="mt-2 text-sm text-neutral-400">
                {camera.manufacturer}
                {metaParts.length > 0 && <> &middot; {metaParts.join(" · ")}</>}
              </p>
            </div>

            <CollectionButtons cameraId={cameraId} />

            {/* Description — scrollable, fixed height */}
            {camera.description && (
              <div className="mt-6">
                <div className="max-h-60 overflow-y-auto pr-2 overscroll-contain">
                  <div className="text-[15px] text-neutral-600 leading-relaxed space-y-4">
                    {camera.description.split("\n\n").map((para, i) => (
                      <p key={i}>{para}</p>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Specs */}
            {hasSpecs && (
              <div className="mt-8">
                <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                  Specifications
                </h2>
                <div className="border border-neutral-100 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <tbody>
                      {Object.entries(camera.specs!).map(([key, value], i) => (
                        <tr
                          key={key}
                          className={i % 2 === 0 ? "bg-neutral-50/50" : "bg-white"}
                        >
                          <td className="px-4 py-2.5 text-neutral-400 font-medium w-2/5">
                            {SPEC_LABELS[key] || key}
                          </td>
                          <td className="px-4 py-2.5 text-neutral-700">
                            {value}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

          </div>

          {/* Pricing — mobile only, order 3 (between specs and ratings) */}
          {hasPricing && (
            <div className="order-3 md:hidden">
              <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                Pricing
              </h2>
              <div className="flex gap-3 flex-wrap">
                {camera.priceMarket != null && (
                  <div className="px-4 py-2.5 bg-neutral-50 rounded-lg">
                    <div className="text-[11px] text-neutral-400 uppercase tracking-wide">
                      Market Value
                    </div>
                    <div className="text-lg font-semibold text-neutral-800 mt-0.5">
                      ~${camera.priceMarket.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </div>
                    {camera.priceMarketSource && (
                      <div className="text-[10px] text-neutral-400 mt-0.5">
                        {PRICE_SOURCE_LABELS[camera.priceMarketSource] || camera.priceMarketSource}
                      </div>
                    )}
                  </div>
                )}
                {camera.priceLaunch != null && (
                  <div className="px-4 py-2.5 bg-neutral-50 rounded-lg">
                    <div className="text-[11px] text-neutral-400 uppercase tracking-wide">
                      Launch Price{camera.year ? ` (${camera.year})` : ""}
                    </div>
                    <div className="text-lg font-semibold text-neutral-800 mt-0.5">
                      ${camera.priceLaunch.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </div>
                    {camera.priceAdjusted != null && (
                      <div className="text-xs text-neutral-400 mt-0.5">
                        ≈ ${camera.priceAdjusted.toLocaleString("en-US")} today
                      </div>
                    )}
                    {camera.priceLaunchSource && (
                      <div className="text-[10px] text-neutral-400 mt-0.5">
                        {PRICE_SOURCE_LABELS[camera.priceLaunchSource] || camera.priceLaunchSource}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Editorial Ratings — order 4 on mobile, right column on desktop */}
          {hasRatings && (
            <div className="order-4 md:col-start-2">
              <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">
                Editorial Ratings
              </h2>
              <div className="space-y-3">
                {Object.entries(camera.ratings!).map(([key, score]) => (
                  <RatingBar
                    key={key}
                    label={RATING_LABELS[key] || key}
                    score={score}
                  />
                ))}
              </div>
            </div>
          )}
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
