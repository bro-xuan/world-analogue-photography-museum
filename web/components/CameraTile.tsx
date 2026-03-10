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
      <div className="aspect-square bg-neutral-100 rounded overflow-hidden">
        <img
          src={camera.thumb ? `/images/${camera.thumb}` : `/images/${camera.image}`}
          alt={camera.name}
          loading="lazy"
          draggable={false}
          className="w-full h-full object-contain select-none"
        />
      </div>
      <p className="text-[10px] text-neutral-400 mt-1 leading-tight truncate text-center">
        {camera.name}
      </p>
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
