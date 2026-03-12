import Link from "next/link";
import { BrandEntry } from "@/lib/brands";

interface BrandTileProps {
  brand: BrandEntry;
}

export default function BrandTile({ brand }: BrandTileProps) {
  return (
    <Link
      href={`/brands/${brand.slug}`}
      className="block group"
    >
      <div
        className="aspect-square border border-neutral-200 rounded-lg flex items-center justify-center group-hover:border-neutral-300 transition-colors bg-white"
        style={{ padding: "max(12px, 1.1vh)" }}
      >
        {brand.logo ? (
          <img
            src={`/${brand.logo}`}
            alt={brand.name}
            loading="lazy"
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <span
            className="font-bold text-black text-center leading-tight uppercase tracking-widest"
            style={{ fontSize: "max(16px, 1.5vh)" }}
          >
            {brand.name}
          </span>
        )}
      </div>
      <div className="flex items-baseline justify-between" style={{ marginTop: "max(6px, 0.55vh)", gap: "max(6px, 0.5vh)" }}>
        <p className="font-medium text-neutral-800 truncate" style={{ fontSize: "max(13px, 1.2vh)" }}>
          {brand.name}
        </p>
        <span className="text-red-400 tabular-nums flex-shrink-0" style={{ fontSize: "max(13px, 1.2vh)" }}>
          {brand.cameraCount}
        </span>
      </div>
    </Link>
  );
}
