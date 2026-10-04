import { useSyncExternalStore } from "react";

export type Cat = "mirror" | "cabinet" | "buddhist" | "art_deco";
export interface Hit {
  pic_id: string; category: Cat; sale_id: number; score: number | null; caption: string | null;
  thumb: string; url: string; why: string | null; first_seen: string | null; hidden: number;
  sale_name?: string; city?: string; sale_state?: string; address?: string; sale_url?: string;
  type_name?: string; start_date?: string; end_date?: string; sale_standout?: number;
  vote: 1 | -1 | null; saved: number;
}
export interface Sale {
  id: number; name: string; org: string; city: string; state: string; address: string; url: string;
  type_name: string; start_date: string; end_date: string; dates_json: string | null; score: number | null;
  standout: number; why: string | null; top_json: string | null; vote: 1 | -1 | null; saved: number; hit_count?: number;
}
export interface CatStat { category: string; up: number; down: number; labeled: number; saved: number; total: number; hidden: number; active: boolean }
export interface Stats { threshold: { labeled: number; each_sign: number }; categories: CatStat[]; sales: CatStat; totals: { hits: number; sales: number; standouts: number } }

let locked = false;
const subs = new Set<() => void>();
const setLocked = () => { locked = true; subs.forEach((f) => f()); };
export const useLocked = () => useSyncExternalStore((f) => (subs.add(f), () => subs.delete(f)), () => locked);

export async function get<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
  const r = await fetch(`/api/${path}${qs.size ? "?" + qs : ""}`, { credentials: "same-origin" });
  if (r.status === 401) { setLocked(); throw new Error("locked"); }
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function postVote(body: Record<string, unknown>) {
  const r = await fetch("/api/vote", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (r.status === 401) { setLocked(); throw new Error("locked"); }
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
}

export const CATS: { id: Cat; label: string; color: string }[] = [
  { id: "mirror", label: "Mirrors", color: "#8FD0CA" },
  { id: "cabinet", label: "Cabinets", color: "#D2915A" },
  { id: "buddhist", label: "Buddhist", color: "#EE8A2E" },
  { id: "art_deco", label: "Art Deco", color: "#E1B24A" },
];
export const catMeta = (c: string) => CATS.find((x) => x.id === c) ?? { id: c as Cat, label: c, color: "#E4EDE4" };

const parseDay = (s?: string | null) => (s ? new Date(s.slice(0, 10) + "T12:00:00") : null);
const fmt = (d: Date) => d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
export function dateRange(s?: string | null, e?: string | null) {
  const a = parseDay(s), b = parseDay(e);
  if (!a && !b) return "Dates not listed";
  const now = new Date(); now.setHours(12, 0, 0, 0);
  if (a && b && a <= now && b >= now) return b.getTime() === now.getTime() ? "On now, last day" : `On now, ends ${fmt(b)}`;
  if (a && b && a.getTime() !== b.getTime()) return `${fmt(a)} to ${fmt(b)}`;
  return fmt((a || b)!);
}
export const mapLink = (x: { address?: string; city?: string; sale_state?: string; state?: string }) => {
  const q = [x.address, x.city, x.sale_state ?? x.state].filter(Boolean).join(", ");
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(q)}`;
};
export const isOnline = (t?: string) => !!t && /online/i.test(t);
