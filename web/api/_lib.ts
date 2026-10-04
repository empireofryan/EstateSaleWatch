import { createHmac, timingSafeEqual } from "node:crypto";
import { createClient } from "@libsql/client/web";
import type { VercelRequest, VercelResponse } from "@vercel/node";

const secret = () => (process.env.APP_SECRET || "").trim();

export const sig = (payload: string) =>
  createHmac("sha256", secret()).update(payload).digest("hex").slice(0, 32);

export const safeEq = (a: string, b: string) => {
  const A = Buffer.from(a), B = Buffer.from(b);
  return A.length === B.length && timingSafeEqual(A, B);
};

let _db: ReturnType<typeof createClient> | null = null;
export const db = () =>
  (_db ??= createClient({
    url: (process.env.TURSO_DATABASE_URL || "").trim(),
    authToken: (process.env.TURSO_AUTH_TOKEN || "").trim(),
  }));

export const rows = async (sql: string, args: (string | number | null)[] = []) =>
  (await db().execute({ sql, args })).rows.map((r) => ({ ...r }) as Record<string, any>);

export function authed(req: VercelRequest): boolean {
  if (!secret()) return false;
  const m = /(?:^|;\s*)esw=([^;]+)/.exec(req.headers.cookie || "");
  if (!m) return false;
  const [exp, s] = decodeURIComponent(m[1]).split(".");
  if (!exp || !s || !/^\d+$/.test(exp)) return false;
  if (Number(exp) <= Date.now() / 1000) return false;
  return safeEq(sig("auth|" + exp), s);
}

export function guard(req: VercelRequest, res: VercelResponse): boolean {
  if (authed(req)) return true;
  res.status(401).json({ error: "locked" });
  return false;
}

export const one = (v: unknown) => (Array.isArray(v) ? String(v[0]) : v == null ? "" : String(v));

export async function upsertVote(
  type: string, id: string, category: string,
  vote: number | null | undefined, saved?: number | null,
) {
  const cur = (await rows(
    "SELECT vote, saved FROM votes WHERE target_type=? AND target_id=? AND category=?",
    [type, id, category],
  ))[0];
  const nv = vote === undefined ? (cur?.vote ?? null) : vote;
  const ns = saved === undefined || saved === null ? (cur?.saved ?? 0) : saved;
  await db().execute({
    sql: `INSERT INTO votes (target_type,target_id,category,vote,saved,updated_at)
          VALUES (?,?,?,?,?,?)
          ON CONFLICT(target_type,target_id,category)
          DO UPDATE SET vote=excluded.vote, saved=excluded.saved, updated_at=excluded.updated_at`,
    args: [type, id, category, nv, ns, new Date().toISOString()],
  });
  return { vote: nv, saved: ns };
}
