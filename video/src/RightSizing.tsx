import React from "react";
import {
  AbsoluteFill,
  Audio,
  staticFile,
  Easing,
  Sequence,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { DISPLAY, SANS, MONO } from "./fonts";

// One palette, one easing, used everywhere. Blue = the model / what we give back. Grey = baseline / waste.
const C = {
  paper: "#f5f5f2",
  tint: "#e3ebf7",
  card: "#ffffff",
  ink: "#111418",
  muted: "#6b7480",
  rule: "#dfe2e6",
  blue: "#2a78d6",
  grey: "#cfd3d8",
  green: "#14966a",
};
const EASE = Easing.bezier(0.22, 1, 0.36, 1);

// Scene timeline (frames @ 30fps)
const S = {
  hook: [0, 105],
  problem: [105, 345],
  stakes: [345, 465],
  solution: [465, 705],
  stat: [705, 855],
  chart: [855, 1035],
  slide: [1035, 1155],
  end: [1155, 1365],
} as const;
export const TOTAL_FRAMES = S.end[1];

const ramp = (f: number, start: number, dur = 18) =>
  interpolate(f, [start, start + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE });

const Rise: React.FC<{ at: number; children: React.ReactNode; dist?: number; style?: React.CSSProperties }> = ({
  at, children, dist = 28, style,
}) => {
  const f = useCurrentFrame();
  const k = ramp(f, at);
  return <div style={{ opacity: k, transform: `translateY(${(1 - k) * dist}px)`, ...style }}>{children}</div>;
};

// Fade a whole scene out over its last frames so cuts feel like one object.
const SceneFade: React.FC<{ len: number; bg: string; children: React.ReactNode }> = ({ len, bg, children }) => {
  const f = useCurrentFrame();
  const out = interpolate(f, [len - 10, len], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const inn = interpolate(f, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: bg }}>
      <AbsoluteFill style={{ opacity: Math.min(out, inn) }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

const Mono: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <span style={{ fontFamily: MONO, fontSize: 30, color: C.muted, letterSpacing: 0.2, ...style }}>{children}</span>
);

/* 1. HOOK — a "reserving" spinner resolves into the title */
const Hook: React.FC = () => {
  const f = useCurrentFrame();
  const spin = f * 9;
  const titleK = ramp(f, 38, 22);
  const reservingOut = 1 - ramp(f, 30, 10);
  return (
    <SceneFade len={S.hook[1] - S.hook[0]} bg={C.paper}>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ position: "absolute", display: "flex", alignItems: "center", gap: 26, opacity: reservingOut }}>
          <svg width="56" height="56" viewBox="0 0 56 56">
            <circle cx="28" cy="28" r="22" stroke={C.rule} strokeWidth="6" fill="none" />
            <path d="M28 6 A22 22 0 0 1 50 28" stroke={C.blue} strokeWidth="6" fill="none" strokeLinecap="round"
              transform={`rotate(${spin} 28 28)`} />
          </svg>
          <span style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 104, color: C.muted, letterSpacing: -3 }}>Reserving</span>
        </div>
        <div style={{ opacity: titleK, transform: `scale(${0.94 + 0.06 * titleK})`, textAlign: "center" }}>
          <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 150, letterSpacing: -6, color: C.ink, lineHeight: 1 }}>
            Right<span style={{ color: C.blue }}>Size</span>
          </div>
          <div style={{ marginTop: 34 }}><Mono>predictive GPU right-sizing · preprint</Mono></div>
        </div>
      </AbsoluteFill>
    </SceneFade>
  );
};

/* Shared scheduler card used by problem + solution demos */
const Card: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div style={{
    position: "absolute", left: 70, right: 70, top: 110, bottom: 110, background: C.card, borderRadius: 34,
    boxShadow: "0 30px 80px rgba(20,40,80,0.10)", padding: "44px 52px", display: "flex", flexDirection: "column", gap: 30,
  }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontFamily: SANS, fontWeight: 600, fontSize: 34, color: C.ink }}>{title} <span style={{ color: C.muted }}>⌄</span></span>
      <span style={{ width: 52, height: 52, borderRadius: 26, background: C.rule, display: "inline-flex", alignItems: "center",
        justifyContent: "center", fontFamily: SANS, fontSize: 24, color: C.muted }}>GPU</span>
    </div>
    {children}
  </div>
);

const Row: React.FC<{ k: string; v: React.ReactNode; at: number; vColor?: string }> = ({ k, v, at, vColor = C.ink }) => (
  <Rise at={at} dist={16}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: `2px solid ${C.rule}`, paddingBottom: 18 }}>
      <span style={{ fontFamily: SANS, fontSize: 34, color: C.muted }}>{k}</span>
      <span style={{ fontFamily: MONO, fontSize: 36, fontWeight: 500, color: vColor }}>{v}</span>
    </div>
  </Rise>
);

// 24 hourly utilisation points for the example pod (illustrative, median need ≈ 0.23 GPU)
const USAGE = [0.17, 0.15, 0.13, 0.12, 0.12, 0.14, 0.18, 0.22, 0.25, 0.24, 0.23, 0.24, 0.26, 0.25, 0.23, 0.22, 0.24, 0.27, 0.28, 0.26, 0.23, 0.21, 0.19, 0.18];

const UsageChart: React.FC<{ at: number; reserved: number; reservedColor: string; label: string }> = ({ at, reserved, reservedColor, label }) => {
  const f = useCurrentFrame();
  const W = 836, H = 330;
  const draw = ramp(f, at, 40);
  const y = (v: number) => H - v * H;
  const pts = USAGE.map((v, i) => [(i / (USAGE.length - 1)) * W, y(v)] as const);
  const shown = Math.max(2, Math.ceil(draw * pts.length));
  const line = pts.slice(0, shown).map(([x, yy], i) => `${i ? "L" : "M"}${x.toFixed(1)},${yy.toFixed(1)}`).join(" ");
  const idleK = ramp(f, at + 40, 20);
  return (
    <div style={{ position: "relative" }}>
      <svg width={W} height={H + 4} viewBox={`0 -2 ${W} ${H + 4}`} style={{ overflow: "visible" }}>
        <rect x={0} y={y(reserved)} width={W} height={H - y(reserved)} fill={reservedColor} opacity={0.10 * idleK} />
        <line x1={0} x2={W} y1={y(reserved)} y2={y(reserved)} stroke={reservedColor} strokeWidth={4} strokeDasharray="12 10" />
        <line x1={0} x2={W} y1={H} y2={H} stroke={C.rule} strokeWidth={2} />
        <path d={line} stroke={C.ink} strokeWidth={5} fill="none" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div style={{ position: "absolute", right: 0, top: y(reserved) + 12, fontFamily: MONO, fontSize: 26, color: reservedColor }}>{label}</div>
      <div style={{ position: "absolute", left: 0, top: H + 14, fontFamily: MONO, fontSize: 24, color: C.muted }}>GPU used, last 24 h</div>
    </div>
  );
};

/* 2. PROBLEM — a pod reserves a whole GPU, uses ~a quarter */
const Problem: React.FC = () => {
  const f = useCurrentFrame();
  const idle = ramp(f, 150, 20);
  return (
    <SceneFade len={S.problem[1] - S.problem[0]} bg={C.tint}>
      <Card title="Scheduler · default">
        <Row k="Pod admitted" v="rec-ranker-7f3" at={8} />
        <Row k="Requested" v="1.0 GPU" at={26} />
        <Rise at={44}><UsageChart at={50} reserved={1} reservedColor={C.muted} label="reserved: 1.0 GPU" /></Rise>
        <div style={{ marginTop: 40, opacity: idle, transform: `translateY(${(1 - idle) * 16}px)` }}>
          <span style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 64, color: C.ink, letterSpacing: -1.5 }}>~79% of it sits idle.</span>
        </div>
        <div style={{ marginTop: "auto" }}><Mono style={{ fontSize: 24 }}>example pod · illustrative</Mono></div>
      </Card>
    </SceneFade>
  );
};

/* 3. STAKES — kinetic text with struck repeats */
const Strike: React.FC<{ at: number; children: string }> = ({ at, children }) => {
  const f = useCurrentFrame();
  const k = ramp(f, at, 14);
  return (
    <span style={{ position: "relative", color: C.blue, opacity: k }}>
      {children}
      <span style={{ position: "absolute", left: 0, top: "54%", height: 7, background: C.blue, width: `${ramp(f, at + 10, 12) * 100}%` }} />
    </span>
  );
};
const Stakes: React.FC = () => (
  <SceneFade len={S.stakes[1] - S.stakes[0]} bg={C.tint}>
    <AbsoluteFill style={{ justifyContent: "center", padding: "0 80px" }}>
      <Rise at={4}>
        <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 92, lineHeight: 1.12, letterSpacing: -2.5, color: C.ink }}>
          AI fleets reserve <Strike at={20}>whole</Strike> whole GPUs, <Strike at={44}>just in case</Strike> just in case, and pay for the idle.
        </div>
      </Rise>
    </AbsoluteFill>
  </SceneFade>
);

/* 4. SOLUTION — Model A sizes it, Model B checks it starts */
const Solution: React.FC = () => {
  const f = useCurrentFrame();
  const shrink = interpolate(f, [120, 150], [1, 0.3], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE });
  const back = ramp(f, 158, 18);
  return (
    <SceneFade len={S.solution[1] - S.solution[0]} bg={C.tint}>
      <Card title="Scheduler · RightSize">
        <Row k="Model A · smallest safe slice" v="0.3 GPU" vColor={C.blue} at={10} />
        <Row k="Model B · start-up risk" v={<span>low <span style={{ color: C.green }}>✓</span></span>} at={46} />
        <Rise at={80}><UsageChart at={84} reserved={shrink} reservedColor={C.blue} label={`allocated: ${shrink.toFixed(1)} GPU`} /></Rise>
        <div style={{ marginTop: 40, opacity: back, transform: `translateY(${(1 - back) * 16}px)` }}>
          <span style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 64, color: C.blue, letterSpacing: -1.5 }}>0.7 GPU handed back.</span>
        </div>
        <div style={{ marginTop: "auto" }}><Mono style={{ fontSize: 24 }}>P90 need + conformal safety margin · example pod</Mono></div>
      </Card>
    </SceneFade>
  );
};

/* 5. STAT — count-up */
const Stat: React.FC = () => {
  const f = useCurrentFrame();
  const n = interpolate(f, [8, 50], [0, 21], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE });
  return (
    <SceneFade len={S.stat[1] - S.stat[0]} bg={C.paper}>
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 80px", gap: 30 }}>
        <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 300, color: C.blue, letterSpacing: -12, lineHeight: 0.9 }}>
          ~{Math.round(n)}%
        </div>
        <Rise at={30}>
          <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 70, lineHeight: 1.1, letterSpacing: -1.5, color: C.ink }}>
            of reserved inference GPU-hours could be reclaimed.
          </div>
        </Rise>
        <Rise at={56}>
          <Mono>≤5% of pods under-provisioned · on clusters never seen in training · Alibaba trace, 155,410 GPUs</Mono>
        </Rise>
      </AbsoluteFill>
    </SceneFade>
  );
};

/* 6. CHART — matched-risk reclaim */
const BARS = [
  { name: "History rule", v: 20.7, color: C.grey },
  { name: "XGBoost", v: 21.9, color: C.grey },
  { name: "Hybrid", v: 22.6, color: C.blue },
];
const Chart: React.FC = () => {
  const f = useCurrentFrame();
  const MAX = 25, W = 560;
  return (
    <SceneFade len={S.chart[1] - S.chart[0]} bg={C.paper}>
      <AbsoluteFill style={{ padding: "150px 80px", gap: 26 }}>
        <Rise at={2}>
          <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 80, lineHeight: 1.05, letterSpacing: -2, color: C.ink }}>
            A simple rule nearly ties machine learning.
          </div>
        </Rise>
        <Rise at={12}><Mono>reclaim at matched 5% risk · mean of 10 held-out clusters</Mono></Rise>
        <div style={{ marginTop: 70, display: "flex", flexDirection: "column", gap: 54 }}>
          {BARS.map((b, i) => {
            const k = ramp(f, 30 + i * 16, 34);
            return (
              <div key={b.name} style={{ display: "flex", alignItems: "center", gap: 28 }}>
                <span style={{ width: 230, flexShrink: 0, fontFamily: SANS, fontSize: 36, color: C.ink, fontWeight: b.color === C.blue ? 600 : 400 }}>{b.name}</span>
                <div style={{ height: 64, flexShrink: 0, width: (b.v / MAX) * W * k, background: b.color, borderRadius: 6 }} />
                <span style={{ fontFamily: MONO, fontSize: 36, fontWeight: 500, color: b.color === C.blue ? C.blue : C.muted, opacity: ramp(f, 50 + i * 16, 14) }}>
                  {(b.v * k).toFixed(1)}%
                </span>
              </div>
            );
          })}
        </div>
        <Rise at={110} style={{ marginTop: 60 }}>
          <div style={{ fontFamily: SANS, fontSize: 38, lineHeight: 1.35, color: C.ink, maxWidth: 880 }}>
            History for known workloads, ML for new ones: <span style={{ color: C.blue, fontWeight: 600 }}>best of both</span>
            <span style={{ fontFamily: MONO, fontSize: 30, color: C.muted }}>  (p = 0.014)</span>
          </div>
        </Rise>
      </AbsoluteFill>
    </SceneFade>
  );
};

/* 7. SLIDE — oversized line drifting across */
const Slide: React.FC = () => {
  const f = useCurrentFrame();
  const len = S.slide[1] - S.slide[0];
  const x = interpolate(f, [0, len], [220, -980], { easing: Easing.inOut(Easing.cubic) });
  return (
    <SceneFade len={len} bg={C.paper}>
      <AbsoluteFill style={{ justifyContent: "center" }}>
        <div style={{ transform: `translateX(${x}px)`, whiteSpace: "nowrap", fontFamily: DISPLAY, fontWeight: 800, fontSize: 200, letterSpacing: -7, lineHeight: 1.02, color: C.ink }}>
          Same inference work,<br />fewer <span style={{ color: C.blue }}>GPUs reserved.</span>
        </div>
      </AbsoluteFill>
    </SceneFade>
  );
};

/* 8. END CARD */
const End: React.FC<{ repoUrl: string }> = ({ repoUrl }) => {
  const f = useCurrentFrame();
  const typed = repoUrl.slice(0, Math.round(interpolate(f, [30, 75], [0, repoUrl.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })));
  const caret = Math.floor(f / 15) % 2 === 0 ? 1 : 0;
  return (
    <AbsoluteFill style={{ background: C.paper, padding: "190px 80px", gap: 56 }}>
      <Rise at={4}>
        <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 132, lineHeight: 0.98, letterSpacing: -5, color: C.ink }}>
          Read the<br />preprint
        </div>
      </Rise>
      <Rise at={18}>
        <div style={{ border: `3px solid ${C.ink}`, padding: "26px 30px", fontFamily: MONO, fontSize: 27, whiteSpace: "nowrap", color: C.ink, background: C.card }}>
          {typed}<span style={{ opacity: caret }}>|</span>
        </div>
      </Rise>
      <Rise at={84}>
        <div style={{ display: "inline-flex", background: C.ink, color: C.paper, fontFamily: SANS, fontWeight: 600, fontSize: 38, padding: "28px 52px" }}>
          Code, data pipeline &amp; paper
        </div>
      </Rise>
      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
        <Rise at={100}>
          <span style={{ fontFamily: SANS, fontSize: 34, color: C.ink, fontWeight: 600 }}>Saksham Adhikari &amp; Sudip Bhandari</span>
        </Rise>
        <Rise at={108}><Mono>Texas State University · data: Alibaba cluster-trace-gpu-v2026</Mono></Rise>
      </div>
    </AbsoluteFill>
  );
};

export const RightSizing: React.FC<{ repoUrl: string }> = ({ repoUrl }) => {
  const seq = (k: keyof typeof S) => ({ from: S[k][0], durationInFrames: S[k][1] - S[k][0] });
  return (
    <AbsoluteFill style={{ background: C.paper }}>
      {/* Original synthesized bed (scripts/make_music.py), mastered to about -24 LUFS */}
      <Audio src={staticFile("music.wav")} />
      <Sequence {...seq("hook")}><Hook /></Sequence>
      <Sequence {...seq("problem")}><Problem /></Sequence>
      <Sequence {...seq("stakes")}><Stakes /></Sequence>
      <Sequence {...seq("solution")}><Solution /></Sequence>
      <Sequence {...seq("stat")}><Stat /></Sequence>
      <Sequence {...seq("chart")}><Chart /></Sequence>
      <Sequence {...seq("slide")}><Slide /></Sequence>
      <Sequence {...seq("end")}><End repoUrl={repoUrl} /></Sequence>
    </AbsoluteFill>
  );
};
