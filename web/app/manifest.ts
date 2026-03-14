import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "World Analog Photography Museum",
    short_name: "AnalogCams",
    description:
      "A living museum of every analog camera and film ever made. Browse thousands of cameras from hundreds of manufacturers.",
    start_url: "/",
    display: "standalone",
    theme_color: "#1a1a1a",
    background_color: "#ffffff",
    icons: [
      {
        src: "/icons/icon-192x192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icons/icon-512x512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
