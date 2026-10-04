import type { VercelRequest, VercelResponse } from "@vercel/node";
import { guard, rows, one } from "./_lib.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (!guard(req, res)) return;
  const saved = one(req.query.saved) === "1", past = one(req.query.past) === "1";
  const w: string[] = [];
  if (saved) w.push("v.saved=1");
  else if (!past) w.push("(s.end_date IS NULL OR substr(s.end_date,1,10) >= date('now','-1 day'))");
  const items = await rows(
    `SELECT s.*, v.vote, COALESCE(v.saved,0) saved,
       (SELECT COUNT(*) FROM hits h WHERE h.sale_id=s.id AND COALESCE(h.hidden,0)=0) hit_count
     FROM sales s LEFT JOIN votes v ON v.target_type='sale' AND v.target_id=CAST(s.id AS TEXT) AND v.category=''
     ${w.length ? "WHERE " + w.join(" AND ") : ""}
     ORDER BY COALESCE(s.standout,0) DESC, s.start_date ASC LIMIT 300`,
  );
  res.setHeader("Cache-Control", "no-store");
  res.json({ items });
}
