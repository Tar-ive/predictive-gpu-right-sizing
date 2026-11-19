// Fonts ship inside the project (public/fonts) so rendering works offline.
import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

const FACES = [
  { family: "Bricolage Grotesque", file: "fonts/BricolageGrotesque.woff2", weight: "200 800" },
  { family: "IBM Plex Sans", file: "fonts/IBMPlexSans.woff2", weight: "100 700" },
  { family: "IBM Plex Mono", file: "fonts/IBMPlexMono-400.woff2", weight: "400" },
  { family: "IBM Plex Mono", file: "fonts/IBMPlexMono-500.woff2", weight: "500" },
];

for (const f of FACES) {
  loadFont({ family: f.family, url: staticFile(f.file), weight: f.weight, format: "woff2" }).catch((err) =>
    console.error(`Could not load ${f.family}`, err),
  );
}

export const DISPLAY = '"Bricolage Grotesque", "Avenir Next", sans-serif';
export const SANS = '"IBM Plex Sans", "Helvetica Neue", sans-serif';
export const MONO = '"IBM Plex Mono", Menlo, monospace';
