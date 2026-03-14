import Link from "next/link";
import { CameraEntry, thumbUrl } from "@/lib/cameras";
import { IMAGE_BASE } from "@/lib/config";

interface CameraTileProps {
  camera: CameraEntry;
  eager?: boolean;
  browse?: boolean;
}

export default function CameraTile({ camera, eager, browse }: CameraTileProps) {
  const content = (
    <>
      <div className="aspect-square rounded overflow-hidden flex items-center justify-center bg-white">
        <img
          src={`${IMAGE_BASE}/${thumbUrl(camera)}`}
          alt={camera.name}
          loading={eager ? "eager" : "lazy"}
          fetchPriority={eager ? "high" : "auto"}
          decoding="async"
          draggable={false}
          className="max-w-full max-h-full object-contain select-none"
        />
      </div>
      <p className="text-neutral-400 mt-1 leading-tight truncate text-center" style={{ fontSize: "max(13px, 1.2vh)" }}>
        {camera.name}
      </p>
      {browse && camera.year && (
        <p className="text-neutral-300 leading-tight truncate text-center" style={{ fontSize: "max(12px, 1.1vh)" }}>
          {camera.year}
        </p>
      )}
    </>
  );

  return (
    <Link
      href={`/cameras/${camera.id}`}
      className={`block camera-link${browse ? " hover:opacity-80 transition-opacity" : ""}`}
      style={{ cursor: "pointer" }}
      draggable={false}
    >
      {content}
    </Link>
  );
}
