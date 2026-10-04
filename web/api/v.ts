import type { VercelRequest, VercelResponse } from "@vercel/node";
import { sig, safeEq, one, upsertVote, authed } from "./_lib.js";
import { page } from "./auth.js";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const t = one(req.query.t), id = one(req.query.id), c = one(req.query.c), v = one(req.query.v), s = one(req.query.s);
  if (!["hit", "sale"].includes(t) || !["1", "-1"].includes(v) || !id ||
      !safeEq(sig(`vote|${t}|${id}|${c}|${v}`), s)) {
    res.status(400).setHeader("content-type", "text/html; charset=utf-8");
    return res.send(page("Vote link is not valid", "Open the app and vote there."));
  }
  await upsertVote(t, id, c, Number(v));
  if (authed(req)) return res.redirect(302, `/?voted=${encodeURIComponent(`${t}:${id}:${v}`)}`);
  res.status(200).setHeader("content-type", "text/html; charset=utf-8");
  res.send(page(Number(v) > 0 ? "Voted up" : "Voted down", "Open the app from your email to browse."));
}
