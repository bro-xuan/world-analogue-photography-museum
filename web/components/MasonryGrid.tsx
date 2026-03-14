import { CameraEntry } from "@/lib/cameras";
import CameraTile from "./CameraTile";

interface MasonryGridProps {
  cameras: CameraEntry[];
}

export default function MasonryGrid({ cameras }: MasonryGridProps) {
  return (
    <div
      id="collection"
      className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-1"
      style={{ gridAutoFlow: "dense" }}
    >
      {cameras.map((camera) => (
        <CameraTile key={camera.id} camera={camera} />
      ))}
    </div>
  );
}
