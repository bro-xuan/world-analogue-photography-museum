import { memo, useCallback } from "react";
import Link from "next/link";
import { CameraEntry, thumbUrl } from "@/lib/cameras";
import { IMAGE_BASE } from "@/lib/config";

interface CameraTileProps {
  camera: CameraEntry;
  eager?: boolean;
  browse?: boolean;
}

export default memo(function CameraTile({ camera, eager, browse }: CameraTileProps) {
  const src = `${IMAGE_BASE}/${thumbUrl(camera)}`;
  const onLoad = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.style.opacity = "1";
  }, []);
  const imgRef = useCallback((el: HTMLImageElement | null) => {
    if (el?.complete) el.style.opacity = "1";
  }, []);
  const content = (
    <>
      <div
        className="aspect-square rounded overflow-hidden flex items-center justify-center"
        style={{ backgroundColor: camera.color || "#ffffff" }}
      >
        <img
          ref={imgRef}
          src={src}
          alt={camera.name}
          width={300}
          height={300}
          loading={eager ? "eager" : "lazy"}
          fetchPriority={eager ? "high" : "auto"}
          decoding="async"
          draggable={false}
          className="tile-img max-w-full max-h-full object-contain select-none"
          style={{ opacity: 0 }}
          onLoad={onLoad}
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
});
