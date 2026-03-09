import Link from "next/link";
import { RelatedCamera } from "@/lib/cameras";

export default function RelatedCameras({
  cameras,
  manufacturer,
}: {
  cameras: RelatedCamera[];
  manufacturer: string;
}) {
  return (
    <section className="mt-16">
      <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">
        More from {manufacturer}
      </h2>
      <div className="flex gap-4 overflow-x-auto pb-4 -mx-6 px-6 snap-x snap-mandatory scrollbar-hide">
        {cameras.map((cam) => (
          <Link
            key={cam.id}
            href={`/cameras/${cam.id}`}
            className="group shrink-0 w-40 snap-start"
          >
            <div className="aspect-square bg-neutral-50 rounded-lg overflow-hidden flex items-center justify-center">
              {cam.image ? (
                <img
                  src={`/images/${cam.image}`}
                  alt={cam.name}
                  className="max-w-full max-h-full object-contain group-hover:scale-105 transition-transform duration-200"
                />
              ) : (
                <div className="text-neutral-300 text-xs">No image</div>
              )}
            </div>
            <p className="mt-2 text-sm text-neutral-700 font-medium truncate group-hover:text-neutral-900 transition-colors">
              {cam.name}
            </p>
            {cam.year && (
              <p className="text-xs text-neutral-400">{cam.year}</p>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}
