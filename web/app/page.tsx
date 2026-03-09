import { loadLandingData, loadAllCameraDetails } from "@/lib/cameras";
import Museum from "@/components/Museum";

export default async function Home() {
  const [data, details] = await Promise.all([
    loadLandingData(),
    loadAllCameraDetails(),
  ]);
  const manufacturers = new Set(data.cameras.map((c) => c.manufacturer)).size;
  const detailIdList = Object.keys(details);

  return (
    <Museum
      cameras={data.cameras}
      total={data.meta.total}
      manufacturers={manufacturers}
      detailIdList={detailIdList}
    />
  );
}
