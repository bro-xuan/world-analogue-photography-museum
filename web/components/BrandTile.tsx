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
      <div className="aspect-square border border-neutral-200 rounded-lg flex items-center justify-center p-5 group-hover:border-neutral-300 transition-colors bg-white">
        {brand.logo ? (
          <img
            src={`/${brand.logo}`}
            alt={brand.name}
            loading="lazy"
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <span className="text-lg font-semibold text-neutral-800 font-display text-center leading-tight">
            {brand.name}
          </span>
        )}
      </div>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-neutral-800 truncate">
          {brand.name}
        </p>
        <span className="text-sm text-red-400 tabular-nums flex-shrink-0">
          {brand.cameraCount}
        </span>
      </div>
      <p className="text-xs text-neutral-400">{brand.slug}</p>
    </Link>
  );
}
