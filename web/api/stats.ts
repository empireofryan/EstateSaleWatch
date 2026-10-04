import type { VercelRequest, VercelResponse } from "@vercel/node";
import { guard, rows } from "./_lib.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (!guard(req, res)) return;
  const votes = await rows(
    `SELECT target_type t, category c, SUM(vote=1) up, SUM(vote=-1) down, SUM(COALESCE(saved,0)) saved
     FROM votes GROUP BY 1,2`);
  const hits = await rows(`SELECT category c, COUNT(*) n, SUM(COALESCE(hidden,0)) hidden FROM hits GROUP BY 1`);
  const sales = (await rows(`SELECT COUNT(*) n, SUM(COALESCE(standout,0)) standouts FROM sales`))[0];
  const THRESH = { labeled: 12, each_sign: 4 };
  const cats = ["mirror", "cabinet", "buddhist", "art_deco"];
  const mk = (t: string, c: string) => {
    const v = votes.find((x) => x.t === t && x.c === c) || {};
    const up = Number(v.up || 0), down = Number(v.down || 0);
    const h = hits.find((x) => x.c === c) || {};
    return { category: c || "sales", up, down, labeled: up + down, saved: Number(v.saved || 0),
      total: Number(h.n || 0), hidden: Number(h.hidden || 0),
      active: up + down >= THRESH.labeled && up >= THRESH.each_sign && down >= THRESH.each_sign };
  };
  res.setHeader("Cache-Control", "no-store");
  res.json({ threshold: THRESH, categories: cats.map((c) => mk("hit", c)), sales: mk("sale", ""),
    totals: { hits: hits.reduce((n, x) => n + Number(x.n), 0), sales: Number(sales?.n || 0), standouts: Number(sales?.standouts || 0) } });
}
