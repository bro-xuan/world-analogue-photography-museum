import { memo, useRef, useCallback } from "react";
import Link from "next/link";
import { CameraEntry, thumbUrl } from "@/lib/cameras";
import { IMAGE_BASE } from "@/lib/config";
import { isLoaded } from "@/lib/imageCache";

interface CameraTileProps {
  camera: CameraEntry;
  eager?: boolean;
  browse?: boolean;
}

export default memo(function CameraTile({ camera, eager, browse }: CameraTileProps) {
  const src = `${IMAGE_BASE}/${thumbUrl(camera)}`;
  const cached = isLoaded(src);
  const imgRef = useRef<HTMLImageElement>(null);
  const onLoad = useCallback(() => {
    if (imgRef.current) imgRef.current.style.opacity = "1";
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
          loading={cached || eager ? "eager" : "lazy"}
          fetchPriority={cached || eager ? "high" : "auto"}
          decoding={cached ? "sync" : "async"}
          draggable={false}
          className="tile-img max-w-full max-h-full object-contain select-none"
          style={{ opacity: cached ? 1 : 0 }}
          onLoad={cached ? undefined : onLoad}
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
