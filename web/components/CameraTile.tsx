import Link from "next/link";
import { CameraEntry } from "@/lib/cameras";

interface CameraTileProps {
  camera: CameraEntry;
  hasDetail: boolean;
  browse?: boolean;
}

export default function CameraTile({ camera, hasDetail, browse }: CameraTileProps) {
  const content = (
    <>
      <div className="aspect-square rounded overflow-hidden flex items-center justify-center">
        <img
          src={camera.thumb ? `/images/${camera.thumb}` : `/images/${camera.image}`}
          alt={camera.name}
          loading="lazy"
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

  if (hasDetail) {
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

  return <div>{content}</div>;
}
