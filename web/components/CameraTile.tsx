import { CameraEntry } from "@/lib/cameras";

interface CameraTileProps {
  camera: CameraEntry;
  hasDetail: boolean;
}

export default function CameraTile({ camera, hasDetail }: CameraTileProps) {
  const content = (
    <>
      <div className="aspect-square bg-neutral-100 rounded overflow-hidden">
        <img
          src={`/images/${camera.image}`}
          alt={camera.name}
          loading="lazy"
          draggable={false}
          className="w-full h-full object-contain select-none"
        />
      </div>
      <p className="text-[10px] text-neutral-400 mt-1 leading-tight truncate">
        {camera.name}
      </p>
    </>
  );

  if (hasDetail) {
    return (
      <a
        href={`/cameras/${camera.id}`}
        className="block camera-link"
        draggable={false}
      >
        {content}
      </a>
    );
  }

  return <div>{content}</div>;
}
