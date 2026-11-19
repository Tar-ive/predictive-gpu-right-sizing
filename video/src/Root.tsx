import React from "react";
import { Composition } from "remotion";
import { z } from "zod";
import { RightSizing, TOTAL_FRAMES } from "./RightSizing";

export const schema = z.object({
  repoUrl: z.string(),
});

export const Root: React.FC = () => (
  <Composition
    id="RightSizing"
    component={RightSizing}
    durationInFrames={TOTAL_FRAMES}
    fps={30}
    width={1080}
    height={1350}
    schema={schema}
    defaultProps={{ repoUrl: "github.com/Tar-ive/predictive-gpu-right-sizing" }}
  />
);
