"use client";

import { useState } from "react";
import Link from "next/link";
import { CameraDetail } from "@/lib/cameras";
import RelatedCameras from "@/components/camera/RelatedCameras";
import CollectionButtons from "@/components/camera/CollectionButtons";
import { IMAGE_BASE } from "@/lib/config";

const SPEC_LABELS: Record<string, string> = {
  type: "Type",
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

function RatingBar({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex items-center" style={{ gap: "max(12px, 1.1vh)" }}>
      <span
        className="text-neutral-500 shrink-0"
        style={{ fontSize: "max(14px, 1.3vh)", width: "max(160px, 14vh)" }}
      >
        {label}
      </span>
      <div
        className="flex-1 bg-neutral-100 rounded-full overflow-hidden"
        style={{ height: "max(6px, 0.55vh)" }}
      >
        <div
          className="h-full bg-neutral-800 rounded-full"
          style={{ width: `${(score / 5) * 100}%` }}
        />
      </div>
      <span
        className="font-medium text-neutral-700 text-right tabular-nums"
        style={{ fontSize: "max(14px, 1.3vh)", width: "max(32px, 3vh)" }}
      >
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
      <main
        className="mx-auto"
        style={{
          maxWidth: "max(900px, 75vw)",
          padding: "max(32px, 3vh) max(24px, 2vw) max(64px, 6vh)",
        }}
      >
        {/* Breadcrumb */}
        <div
          className="flex items-center"
          style={{ gap: "max(6px, 0.6vh)", fontSize: "max(14px, 1.3vh)", marginBottom: "max(24px, 2.2vh)" }}
        >
          <Link
            href={`/brands/${camera.manufacturer.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`}
            className="text-neutral-400 hover:text-neutral-900 transition-colors"
          >
            {camera.manufacturer}
          </Link>
          <span className="text-neutral-300">/</span>
          <span className="text-neutral-600 truncate">{camera.name}</span>
        </div>

        {/* Main grid */}
        <div
          className="grid grid-cols-1 md:grid-cols-[1fr_1fr] lg:grid-cols-[5fr_6fr]"
          style={{ gap: "max(40px, 3.5vh) max(56px, 4vh)" }}
        >
          {/* Image + thumbnails */}
          <div className="order-1 md:sticky md:self-start md:row-span-3" style={{ top: "max(80px, 7vh)" }}>
            <div className="flex items-center justify-center">
              {validImages.length > 0 ? (
                <img
                  src={`${IMAGE_BASE}/${validImages[safeActive]}`}
                  alt={camera.name}
                  className="w-full h-auto object-contain"
                  onError={() => handleImageError(validImages[safeActive])}
                />
              ) : (
                <div className="aspect-square w-full flex items-center justify-center text-neutral-300" style={{ fontSize: "max(14px, 1.3vh)" }}>
                  No image available
                </div>
              )}
            </div>

            {/* Thumbnail strip */}
            {validImages.length > 1 && (
              <div className="flex" style={{ gap: "max(8px, 0.7vh)", marginTop: "max(12px, 1.1vh)" }}>
                {validImages.map((img, i) => (
                  <button
                    key={img}
                    onClick={() => setActiveImage(i)}
                    className={`rounded-lg overflow-hidden border-2 transition-colors cursor-pointer ${
                      i === safeActive
                        ? "border-neutral-900"
                        : "border-transparent hover:border-neutral-300"
                    }`}
                    style={{ width: "max(56px, 5vh)", height: "max(56px, 5vh)" }}
                  >
                    <img
                      src={`${IMAGE_BASE}/${img}`}
                      alt=""
                      className="w-full h-full object-contain bg-neutral-50"
                      onError={() => handleImageError(img)}
                    />
                  </button>
                ))}
              </div>
            )}

            {/* Pricing — under photo on desktop */}
            {hasPricing && (
              <div className="hidden md:block" style={{ marginTop: "max(24px, 2.2vh)" }}>
                <h2
                  className="font-semibold text-neutral-400 uppercase"
                  style={{ fontSize: "max(13px, 1.2vh)", letterSpacing: "0.05em", marginBottom: "max(12px, 1.1vh)" }}
                >
                  Pricing
                </h2>
                <div className="flex flex-wrap" style={{ gap: "max(12px, 1.1vh)" }}>
                  {camera.priceMarket != null && (
                    <div className="bg-neutral-50 rounded-lg" style={{ padding: "max(10px, 1vh) max(16px, 1.5vh)" }}>
                      <div className="text-neutral-400 uppercase" style={{ fontSize: "max(12px, 1.1vh)", letterSpacing: "0.04em" }}>
                        Market Value
                      </div>
                      <div
                        className="font-semibold text-neutral-800"
                        style={{ fontSize: "max(18px, 1.8vh)", marginTop: "max(2px, 0.2vh)" }}
                      >
                        ~${camera.priceMarket.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </div>
                    </div>
                  )}
                  {camera.priceLaunch != null && (
                    <div className="bg-neutral-50 rounded-lg" style={{ padding: "max(10px, 1vh) max(16px, 1.5vh)" }}>
                      <div className="text-neutral-400 uppercase" style={{ fontSize: "max(12px, 1.1vh)", letterSpacing: "0.04em" }}>
                        Launch Price{camera.year ? ` (${camera.year})` : ""}
                      </div>
                      <div
                        className="font-semibold text-neutral-800"
                        style={{ fontSize: "max(18px, 1.8vh)", marginTop: "max(2px, 0.2vh)" }}
                      >
                        ${camera.priceLaunch.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right column: name → description → specs */}
          <div className="order-2">
            {/* Header */}
            <div>
              <h1
                className="font-display font-bold text-neutral-900 leading-tight"
                style={{ fontSize: "max(28px, 2.8vh)" }}
              >
                {camera.name}
              </h1>
              <p className="text-neutral-400" style={{ marginTop: "max(8px, 0.7vh)", fontSize: "max(14px, 1.3vh)" }}>
                {camera.manufacturer}
                {metaParts.length > 0 && <> &middot; {metaParts.join(" · ")}</>}
              </p>
            </div>

            <CollectionButtons cameraId={cameraId} />

            {/* Description */}
            {camera.description && (
              <div style={{ marginTop: "max(24px, 2.2vh)" }}>
                <div
                  className="overflow-y-auto pr-2 overscroll-contain"
                  style={{ maxHeight: "max(240px, 22vh)" }}
                >
                  <div className="text-neutral-600 leading-relaxed space-y-4" style={{ fontSize: "max(15px, 1.4vh)" }}>
                    {camera.description.split("\n\n").map((para, i) => (
                      <p key={i}>{para}</p>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Specs */}
            {hasSpecs && (
              <div style={{ marginTop: "max(32px, 3vh)" }}>
                <h2
                  className="font-semibold text-neutral-400 uppercase"
                  style={{ fontSize: "max(13px, 1.2vh)", letterSpacing: "0.05em", marginBottom: "max(12px, 1.1vh)" }}
                >
                  Specifications
                </h2>
                <div className="border border-neutral-100 rounded-lg overflow-hidden">
                  <table className="w-full" style={{ fontSize: "max(14px, 1.3vh)" }}>
                    <tbody>
                      {Object.entries(camera.specs!).map(([key, value], i) => (
                        <tr
                          key={key}
                          className={i % 2 === 0 ? "bg-neutral-50/50" : "bg-white"}
                        >
                          <td
                            className="text-neutral-400 font-medium w-2/5"
                            style={{ padding: "max(10px, 0.9vh) max(16px, 1.4vh)" }}
                          >
                            {SPEC_LABELS[key] || key}
                          </td>
                          <td
                            className="text-neutral-700"
                            style={{ padding: "max(10px, 0.9vh) max(16px, 1.4vh)" }}
                          >
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

          {/* Pricing — mobile only */}
          {hasPricing && (
            <div className="order-3 md:hidden">
              <h2
                className="font-semibold text-neutral-400 uppercase"
                style={{ fontSize: "max(13px, 1.2vh)", letterSpacing: "0.05em", marginBottom: "max(12px, 1.1vh)" }}
              >
                Pricing
              </h2>
              <div className="flex flex-wrap" style={{ gap: "max(12px, 1.1vh)" }}>
                {camera.priceMarket != null && (
                  <div className="bg-neutral-50 rounded-lg" style={{ padding: "max(10px, 1vh) max(16px, 1.5vh)" }}>
                    <div className="text-neutral-400 uppercase" style={{ fontSize: "max(12px, 1.1vh)", letterSpacing: "0.04em" }}>
                      Market Value
                    </div>
                    <div
                      className="font-semibold text-neutral-800"
                      style={{ fontSize: "max(18px, 1.8vh)", marginTop: "max(2px, 0.2vh)" }}
                    >
                      ~${camera.priceMarket.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </div>
                  </div>
                )}
                {camera.priceLaunch != null && (
                  <div className="bg-neutral-50 rounded-lg" style={{ padding: "max(10px, 1vh) max(16px, 1.5vh)" }}>
                    <div className="text-neutral-400 uppercase" style={{ fontSize: "max(12px, 1.1vh)", letterSpacing: "0.04em" }}>
                      Launch Price{camera.year ? ` (${camera.year})` : ""}
                    </div>
                    <div
                      className="font-semibold text-neutral-800"
                      style={{ fontSize: "max(18px, 1.8vh)", marginTop: "max(2px, 0.2vh)" }}
                    >
                      ${camera.priceLaunch.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Editorial Ratings */}
          {hasRatings && (
            <div className="order-4 md:col-start-2">
              <h2
                className="font-semibold text-neutral-400 uppercase"
                style={{ fontSize: "max(13px, 1.2vh)", letterSpacing: "0.05em", marginBottom: "max(12px, 1.1vh)" }}
              >
                Editorial Ratings
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "max(12px, 1.1vh)" }}>
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

        {/* Support CTA */}
        <div
          className="flex items-center justify-center border-t border-neutral-100"
          style={{ marginTop: "max(48px, 4.5vh)", paddingTop: "max(32px, 3vh)" }}
        >
          <a
            href="/support"
            className="inline-flex items-center text-neutral-400 hover:text-neutral-600 transition-colors"
            style={{ gap: "max(6px, 0.6vh)", fontSize: "max(14px, 1.3vh)" }}
          >
            <img src="https://storage.ko-fi.com/cdn/cup-border.png" alt="" style={{ width: "max(18px, 1.7vh)", height: "max(18px, 1.7vh)" }} />
            Enjoy this museum? Support on Ko-fi
          </a>
        </div>
      </main>
    </div>
  );
}
