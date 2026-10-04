import type { VercelRequest, VercelResponse } from "@vercel/node";
import { guard, rows, one } from "../_lib.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (!guard(req, res)) return;
  const id = one(req.query.id);
  const sale = (await rows(
    `SELECT s.*, v.vote, COALESCE(v.saved,0) saved FROM sales s
     LEFT JOIN votes v ON v.target_type='sale' AND v.target_id=CAST(s.id AS TEXT) AND v.category=''
     WHERE s.id=?`, [id]))[0];
  if (!sale) return res.status(404).json({ error: "not found" });
  const hits = await rows(
    `SELECT h.pic_id,h.category,h.sale_id,h.score,h.caption,h.thumb,h.url,h.why,h.first_seen,COALESCE(h.hidden,0) hidden,
            v.vote, COALESCE(v.saved,0) saved
     FROM hits h LEFT JOIN votes v ON v.target_type='hit' AND v.target_id=h.pic_id AND v.category=h.category
     WHERE h.sale_id=? ORDER BY h.score DESC`, [id]);
  res.setHeader("Cache-Control", "no-store");
  res.json({ sale, hits });
}
