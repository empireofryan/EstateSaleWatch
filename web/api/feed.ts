import type { VercelRequest, VercelResponse } from "@vercel/node";
import { guard, rows, one } from "./_lib.js";

const ACTIVE = "(s.end_date IS NULL OR substr(s.end_date,1,10) >= date('now','-1 day'))";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (!guard(req, res)) return;
  const q = req.query;
  const category = one(q.category), state = one(q.state) || "new", since = one(q.since);
  const saved = one(q.saved) === "1", hidden = one(q.hidden) === "1", standout = one(q.standout) === "1";
  const past = one(q.past) === "1";
  const limit = Math.min(Math.max(Number(one(q.limit)) || 60, 1), 200);
  const offset = Math.max(Number(one(q.offset)) || 0, 0);

  const w: string[] = [], a: (string | number)[] = [];
  if (category) { w.push("h.category=?"); a.push(category); }
  if (!hidden) w.push("COALESCE(h.hidden,0)=0");
  if (standout) w.push("s.standout=1");
  if (since) { w.push("h.first_seen>=?"); a.push(since); }
  if (saved) w.push("v.saved=1");
  else {
    if (state === "new") w.push("v.vote IS NULL AND COALESCE(v.saved,0)=0");
    else if (state === "up") w.push("v.vote=1");
    else if (state === "down") w.push("v.vote=-1");
    if ((state === "new" || state === "all") && !past) w.push(ACTIVE);
  }
  const where = w.length ? "WHERE " + w.join(" AND ") : "";
  const items = await rows(
    `SELECT h.pic_id,h.category,h.sale_id,h.score,h.model_score,h.caption,h.thumb,h.url,h.why,h.first_seen,
            COALESCE(h.hidden,0) hidden, s.name sale_name,s.city,s.state sale_state,s.address,s.url sale_url,
            s.type_name,s.start_date,s.end_date,COALESCE(s.standout,0) sale_standout,
            v.vote, COALESCE(v.saved,0) saved
     FROM hits h LEFT JOIN sales s ON s.id=h.sale_id
     LEFT JOIN votes v ON v.target_type='hit' AND v.target_id=h.pic_id AND v.category=h.category
     ${where} ORDER BY h.first_seen DESC, h.score DESC LIMIT ? OFFSET ?`,
    [...a, limit, offset],
  );
  let standouts: Record<string, any>[] = [];
  if (one(q.standouts) === "1") {
    standouts = await rows(
      `SELECT s.*, v.vote, COALESCE(v.saved,0) saved FROM sales s
       LEFT JOIN votes v ON v.target_type='sale' AND v.target_id=CAST(s.id AS TEXT) AND v.category=''
       WHERE s.standout=1 AND ${ACTIVE} AND (v.vote IS NULL OR v.vote=1)
       ORDER BY s.score DESC LIMIT 12`,
    );
  }
  res.setHeader("Cache-Control", "no-store");
  res.json({ items, standouts, hasMore: items.length === limit });
}
