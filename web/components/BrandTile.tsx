import Link from "next/link";
import { BrandEntry } from "@/lib/brands";

interface BrandTileProps {
  brand: BrandEntry;
}

export default function BrandTile({ brand }: BrandTileProps) {
  return (
    <Link
      href={`/brands/${brand.slug}`}
      className="block group hover:opacity-90 transition-opacity"
    >
      <div className="aspect-square bg-neutral-100 rounded-lg overflow-hidden">
        <img
          src={`/images/${brand.heroImage}`}
          alt={brand.name}
          loading="lazy"
          className="w-full h-full object-contain"
        />
      </div>
      <div className="mt-2">
        {brand.logo ? (
          <div className="h-5 flex items-center">
            <img
              src={`/${brand.logo}`}
              alt={brand.name}
              className="max-h-full max-w-full object-contain brightness-0"
            />
          </div>
        ) : (
          <p className="text-sm font-medium text-neutral-800 truncate group-hover:text-neutral-600 transition-colors font-display">
            {brand.name}
          </p>
        )}
        <p className="text-xs text-neutral-400 mt-0.5">
          {brand.cameraCount} camera{brand.cameraCount !== 1 ? "s" : ""}
          {brand.country && <> &middot; {brand.country}</>}
        </p>
      </div>
    </Link>
  );
}
