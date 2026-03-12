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
    <section style={{ marginTop: "max(64px, 6vh)" }}>
      <h2
        className="font-semibold text-neutral-400 uppercase"
        style={{ fontSize: "max(13px, 1.2vh)", letterSpacing: "0.05em", marginBottom: "max(16px, 1.5vh)" }}
      >
        More from {manufacturer}
      </h2>
      <div
        className="flex overflow-x-auto pb-4 -mx-6 px-6 snap-x snap-mandatory scrollbar-hide"
        style={{ gap: "max(16px, 1.5vh)" }}
      >
        {cameras.map((cam) => (
          <Link
            key={cam.id}
            href={`/cameras/${cam.id}`}
            className="group shrink-0 snap-start"
            style={{ width: "max(160px, 14vh)" }}
          >
            <div className="aspect-square bg-neutral-50 rounded-lg overflow-hidden flex items-center justify-center">
              {cam.image ? (
                <img
                  src={`/images/${cam.image}`}
                  alt={cam.name}
                  className="max-w-full max-h-full object-contain group-hover:scale-105 transition-transform duration-200"
                />
              ) : (
                <div className="text-neutral-300" style={{ fontSize: "max(12px, 1.1vh)" }}>
                  No image
                </div>
              )}
            </div>
            <p
              className="text-neutral-700 font-medium truncate group-hover:text-neutral-900 transition-colors"
              style={{ marginTop: "max(8px, 0.7vh)", fontSize: "max(14px, 1.3vh)" }}
            >
              {cam.name}
            </p>
            {cam.year && (
              <p className="text-neutral-400" style={{ fontSize: "max(12px, 1.1vh)" }}>
                {cam.year}
              </p>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}
