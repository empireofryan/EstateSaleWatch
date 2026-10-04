import type { VercelRequest, VercelResponse } from "@vercel/node";
import { guard, upsertVote } from "./_lib.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (!guard(req, res)) return;
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const b = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
  const type = b.target_type, id = String(b.target_id ?? ""), cat = type === "sale" ? "" : String(b.category ?? "");
  if (!["hit", "sale"].includes(type) || !id) return res.status(400).json({ error: "bad target" });
  if (type === "hit" && !cat) return res.status(400).json({ error: "category required" });
  const vote = "vote" in b ? (b.vote === null ? null : [1, -1].includes(b.vote) ? b.vote : undefined) : undefined;
  if ("vote" in b && vote === undefined) return res.status(400).json({ error: "bad vote" });
  const saved = "saved" in b ? (b.saved ? 1 : 0) : undefined;
  res.json(await upsertVote(type, id, cat, vote, saved));
}
