import type { VercelRequest, VercelResponse } from "@vercel/node";
import { sig, safeEq, one } from "./_lib.js";

export default function handler(req: VercelRequest, res: VercelResponse) {
  const exp = one(req.query.exp), s = one(req.query.s);
  let to = one(req.query.to) || "/";
  if (!to.startsWith("/") || to.startsWith("//") || to.startsWith("/api")) to = "/";
  if (!/^\d+$/.test(exp) || Number(exp) <= Date.now() / 1000 || !safeEq(sig("auth|" + exp), s)) {
    res.status(401).setHeader("content-type", "text/html; charset=utf-8");
    return res.send(page("This link is expired or invalid", "Open the newest link in your daily email."));
  }
  const maxAge = Math.floor(Number(exp) - Date.now() / 1000);
  res.setHeader("Set-Cookie", `esw=${exp}.${sig("auth|" + exp)}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`);
  res.redirect(302, to);
}

export const page = (h: string, p: string) =>
  `<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>${h}</title>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#0F3A45;color:#E4EDE4;font:18px/1.5 system-ui;text-align:center;padding:24px">
<div><h1 style="font-weight:600;font-size:22px;color:#D6A53A">${h}</h1><p>${p}</p></div>`;
