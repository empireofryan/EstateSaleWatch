import type { Cat } from "./api";

export function CatGlyph({ cat, size = 18 }: { cat: Cat | string; size?: number }) {
  const p = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinejoin: "round" as const, strokeLinecap: "round" as const, "aria-hidden": true };
  switch (cat) {
    case "mirror": return <svg {...p}><path d="M7 21V9a5 5 0 0 1 10 0v12z" /><path d="M10 9.5a2 2 0 0 1 2-2" /></svg>;
    case "cabinet": return <svg {...p}><rect x="4" y="3" width="16" height="17" /><path d="M12 3v17M4 11h16M9.5 7v1.5M14.5 7v1.5M9.5 14.5V16M14.5 14.5V16M6 20v1.5M18 20v1.5" /></svg>;
    case "buddhist": return <svg {...p}><path d="M12 3c1 2 1 3 0 4-1-1-1-2 0-4zM12 20c-4 0-8-3-9-8 3 0 6 1 9 4 3-3 6-4 9-4-1 5-5 8-9 8z" /><path d="M12 16c-2-2-2-5 0-8 2 3 2 6 0 8z" /></svg>;
    case "art_deco": return <svg {...p}><path d="M12 21 3 11a13 13 0 0 1 18 0z" /><path d="M12 21V8.5M12 21 7 9.7M12 21l5-11.3" /></svg>;
    default: return <svg {...p}><circle cx="12" cy="12" r="8" /></svg>;
  }
}

export const IconUp = ({ on }: { on?: boolean }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill={on ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" aria-hidden>
    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
  </svg>
);
export const IconDown = ({ on }: { on?: boolean }) => <span style={{ display: "inline-flex", transform: "rotate(180deg)" }}><IconUp on={on} /></span>;
export const IconSave = ({ on }: { on?: boolean }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill={on ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden>
    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
  </svg>
);

/** Sunburst fan used in the masthead. */
export function Fan() {
  const rays = Array.from({ length: 17 }, (_, i) => -80 + i * 10);
  return (
    <svg className="fan" viewBox="0 0 200 110" aria-hidden>
      <g transform="translate(100 108)">
        {rays.map((a, i) => (
          <path key={a} className="ray" style={{ ["--i" as string]: i }} d="M0 0 L-5 -104 A104 104 0 0 1 5 -104 Z" transform={`rotate(${a})`} />
        ))}
        <path d="M-34 0a34 34 0 0 1 68 0z" className="fan-hub" />
        <path d="M-20 0a20 20 0 0 1 40 0z" className="fan-hub2" />
      </g>
    </svg>
  );
}

/** Eight-spoke dharma wheel. `lit` spokes glow. */
export function Wheel({ lit, active, color }: { lit: number; active: boolean; color: string }) {
  return (
    <svg className={"wheel" + (active ? " spin" : "")} viewBox="0 0 100 100" aria-hidden style={{ ["--c" as string]: color }}>
      <circle cx="50" cy="50" r="46" className="w-rim" />
      <circle cx="50" cy="50" r="38" className="w-rim2" />
      {Array.from({ length: 8 }, (_, i) => (
        <g key={i} transform={`rotate(${i * 45} 50 50)`} className={i < lit ? "spoke on" : "spoke"}>
          <path d="M50 12 L54 40 L50 46 L46 40 Z" />
          <circle cx="50" cy="8" r="2.6" />
        </g>
      ))}
      <circle cx="50" cy="50" r="9" className="w-hub" />
      <circle cx="50" cy="50" r="3.5" className="w-eye" />
    </svg>
  );
}
