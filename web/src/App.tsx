import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CATS, catMeta, dateRange, get, isOnline, mapLink, postVote, useLocked, type Cat, type CatStat, type Hit, type Sale, type Stats } from "./api";
import { CatGlyph, Fan, Wheel } from "./Glyphs";
import { Lightbox, Plate, SaleActs, topPics, type Patch } from "./components";

/* ---------- tiny router ---------- */
function usePath() {
  const [p, setP] = useState(location.pathname);
  useEffect(() => { const f = () => setP(location.pathname); addEventListener("popstate", f); return () => removeEventListener("popstate", f); }, []);
  const go = useCallback((to: string) => { history.pushState({}, "", to); setP(location.pathname); window.scrollTo(0, 0); }, []);
  return [p, go] as const;
}

/* ---------- toast ---------- */
function useToast() {
  const [msg, setMsg] = useState("");
  const t = useRef<number>(0);
  const show = useCallback((m: string) => { setMsg(m); clearTimeout(t.current); t.current = window.setTimeout(() => setMsg(""), 2600); }, []);
  return [msg, show] as const;
}

function useKeys(map: Record<string, () => void>, on = true) {
  const ref = useRef(map); ref.current = map;
  useEffect(() => {
    if (!on) return;
    const f = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey || /INPUT|TEXTAREA|SELECT/.test(t.tagName)) return;
      const fn = ref.current[e.key];
      if (fn) { e.preventDefault(); fn(); }
    };
    addEventListener("keydown", f); return () => removeEventListener("keydown", f);
  }, [on]);
}

/* ---------- hit list shared by feed, saved, sale page ---------- */
function useHitActions(items: Hit[], setItems: (f: (a: Hit[]) => Hit[]) => void, toast: (m: string) => void, refresh?: () => void) {
  return useCallback((it: Hit, p: Patch) => {
    const prev = { vote: it.vote, saved: it.saved };
    const apply = (q: Patch) => setItems((a) => a.map((x) => x.pic_id === it.pic_id && x.category === it.category ? { ...x, ...q } as Hit : x));
    apply(p);
    postVote({ target_type: "hit", target_id: it.pic_id, category: it.category, ...p }).then(() => {
      if (p.vote === 1) toast("Loved. Taste model noted.");
      else if (p.vote === -1) toast("Passed. Taste model noted.");
      else if (p.vote === null) toast("Vote cleared");
      else if (p.saved !== undefined) toast(p.saved ? "Saved to go see" : "Removed from saved");
      refresh?.();
    }).catch(() => { apply(prev); toast("Could not save that. Try again."); });
  }, [setItems, toast, refresh]);
}

function HitGrid({ items, setItems, toast, showSale = true, onSale, emptyMsg, footer }: {
  items: Hit[]; setItems: (f: (a: Hit[]) => Hit[]) => void; toast: (m: string) => void; showSale?: boolean;
  onSale: (id: number) => void; emptyMsg: React.ReactNode; footer?: React.ReactNode;
}) {
  const [sel, setSel] = useState(-1);
  const [open, setOpen] = useState<number | null>(null);
  const act = useHitActions(items, setItems, toast);
  const cur = open ?? sel;
  const move = (d: number) => {
    const n = Math.min(items.length - 1, Math.max(0, (cur < 0 ? (d > 0 ? -1 : items.length) : cur) + d));
    if (open !== null) setOpen(n); setSel(n);
    if (open === null) document.querySelector(`[data-idx="${n}"]`)?.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };
  const doAct = (p: (it: Hit) => Patch) => { const it = items[cur]; if (it) act(it, p(it)); };
  useKeys({
    j: () => move(1), k: () => move(-1), ArrowRight: () => open !== null && move(1), ArrowLeft: () => open !== null && move(-1),
    u: () => doAct((i) => ({ vote: i.vote === 1 ? null : 1 })),
    d: () => doAct((i) => ({ vote: i.vote === -1 ? null : -1 })),
    s: () => doAct((i) => ({ saved: i.saved ? 0 : 1 })),
    Enter: () => { if (open === null && sel >= 0) setOpen(sel); },
    Escape: () => setOpen(null),
  });
  if (!items.length) return <div className="empty">{emptyMsg}</div>;
  return (
    <>
      <div className="grid">
        {items.map((it, i) => (
          <Plate key={it.pic_id + it.category} idx={i} it={it} showSale={showSale} selected={i === sel}
            dim={it.vote !== null && it.vote !== undefined} onOpen={() => { setSel(i); setOpen(i); }} onAct={(p) => act(it, p)} />
        ))}
      </div>
      {footer}
      {open !== null && items[open] && (
        <Lightbox it={items[open]} onClose={() => setOpen(null)} onAct={(p) => act(items[open], p)} onStep={move}
          onSale={(id) => { setOpen(null); onSale(id); }} />
      )}
    </>
  );
}

function useSaleActions(setSales: (f: (a: Sale[]) => Sale[]) => void, toast: (m: string) => void) {
  return useCallback((s: Sale, p: Patch) => {
    const prev = { vote: s.vote, saved: s.saved };
    const apply = (q: Patch) => setSales((a) => a.map((x) => (x.id === s.id ? { ...x, ...q } as Sale : x)));
    apply(p);
    postVote({ target_type: "sale", target_id: String(s.id), category: "", ...p })
      .then(() => toast(p.saved !== undefined ? (p.saved ? "Sale saved" : "Sale removed from saved") : p.vote === null ? "Vote cleared" : p.vote === 1 ? "Sale loved" : "Sale passed"))
      .catch(() => { apply(prev); toast("Could not save that. Try again."); });
  }, [setSales, toast]);
}

/* ---------- sale tile ---------- */
function SaleTile({ s, go, wide, onAct }: { s: Sale; go: (p: string) => void; wide?: boolean; onAct: (p: Patch) => void }) {
  const pics = topPics(s).slice(0, 3);
  return (
    <article className={"sale" + (s.standout ? " standout" : "") + (wide ? " wide" : "")}>
      <button className="sale-main" onClick={() => go("/sales/" + s.id)}>
        <span className="strip">{pics.length ? pics.map((p, i) => <img key={i} src={p.thumb} alt="" loading="lazy" />) : <span className="nopic" />}</span>
        <span className="sale-body">
          <b>{s.name}</b>
          <span className="sub">{[s.city, dateRange(s.start_date, s.end_date)].filter(Boolean).join(", ")}{isOnline(s.type_name) ? ", online" : ""}</span>
          {s.why ? <span className="why">{s.why}</span> : null}
          {s.hit_count ? <span className="count">{s.hit_count} {s.hit_count === 1 ? "find" : "finds"}</span> : null}
        </span>
      </button>
      <SaleActs s={s} onAct={onAct} />
    </article>
  );
}

/* ---------- views ---------- */
type StateF = "new" | "up" | "down" | "all";
function FeedView({ toast, go }: { toast: (m: string) => void; go: (p: string) => void }) {
  const [cat, setCat] = useState<string>("");
  const [state, setState] = useState<StateF>("new");
  const [hidden, setHidden] = useState(false);
  const [items, setItems] = useState<Hit[]>([]);
  const [standouts, setStandouts] = useState<Sale[]>([]);
  const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);
  const setSales = useCallback((f: (a: Sale[]) => Sale[]) => setStandouts(f), []);
  const sAct = useSaleActions(setSales, toast);

  const load = useCallback(async (offset: number) => {
    setLoading(true); setErr(false);
    try {
      const r = await get<{ items: Hit[]; standouts: Sale[]; hasMore: boolean }>("feed", { category: cat, state, hidden: hidden ? 1 : 0, offset, standouts: offset === 0 ? 1 : 0 });
      setItems((a) => (offset ? [...a, ...r.items] : r.items));
      if (offset === 0) setStandouts(r.standouts);
      setMore(r.hasMore);
    } catch (e) { if ((e as Error).message !== "locked") setErr(true); }
    setLoading(false);
  }, [cat, state, hidden]);
  useEffect(() => { load(0); }, [load]);

  return (
    <>
      <div className="filters">
        <div className="chips" role="group" aria-label="Category">
          <button className={"chip" + (cat === "" ? " on" : "")} aria-pressed={cat === ""} onClick={() => setCat("")}>All</button>
          {CATS.map((c) => (
            <button key={c.id} className={"chip" + (cat === c.id ? " on" : "")} aria-pressed={cat === c.id} style={{ ["--c" as string]: c.color }} onClick={() => setCat(c.id)}>
              <CatGlyph cat={c.id} size={16} />{c.label}
            </button>
          ))}
        </div>
        <div className="row2">
          <div className="seg" role="group" aria-label="Show">
            {([["new", "New"], ["up", "Loved"], ["down", "Passed"], ["all", "All"]] as const).map(([k, l]) => (
              <button key={k} className={state === k ? "on" : ""} aria-pressed={state === k} onClick={() => setState(k)}>{l}</button>
            ))}
          </div>
          <label className="toggle" title="Show finds the taste model hid"><input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} /><span className="box" />Show hidden</label>
        </div>
      </div>

      {standouts.length > 0 && state !== "down" && (
        <section className="pinned" aria-label="Standout sales">
          <h2 className="sec">Standout sales</h2>
          <div className="rail">{standouts.map((s) => <SaleTile key={s.id} s={s} go={go} wide onAct={(p) => sAct(s, p)} />)}</div>
        </section>
      )}

      {err ? <div className="empty">Could not load finds. <button className="lnk" onClick={() => load(0)}>Try again</button></div> :
        loading && !items.length ? <div className="grid">{Array.from({ length: 6 }, (_, i) => <div key={i} className="plate skel"><div className="frame"><div className="inner"><div className="photo" /></div></div></div>)}</div> :
        <HitGrid items={items} setItems={setItems} toast={toast} onSale={(id) => go("/sales/" + id)}
          emptyMsg={state === "new" ? <><h3>Nothing new to review</h3><p>The scanner runs daily. Check Saved, or switch to All to revisit old finds.</p></> : <><h3>No finds here yet</h3><p>Change the filters or vote on a few finds first.</p></>}
          footer={more ? <button className="more" onClick={() => load(items.length)} disabled={loading}>{loading ? "Loading" : "Load more finds"}</button> : null} />}
    </>
  );
}

function SalesView({ go, toast }: { go: (p: string) => void; toast: (m: string) => void }) {
  const [items, setItems] = useState<Sale[]>([]);
  const [past, setPast] = useState(false);
  const [loading, setLoading] = useState(true);
  const sAct = useSaleActions(setItems, toast);
  useEffect(() => { setLoading(true); get<{ items: Sale[] }>("sales", { past: past ? 1 : 0 }).then((r) => setItems(r.items)).catch(() => {}).finally(() => setLoading(false)); }, [past]);
  const std = items.filter((s) => s.standout), rest = items.filter((s) => !s.standout);
  return (
    <>
      <div className="filters"><div className="row2"><h1 className="pg">Sales</h1>
        <label className="toggle"><input type="checkbox" checked={past} onChange={(e) => setPast(e.target.checked)} /><span className="box" />Include ended sales</label></div></div>
      {!loading && !items.length && <div className="empty"><h3>No sales yet</h3><p>Upcoming and active sales appear after the next scan.</p></div>}
      {std.length > 0 && <><h2 className="sec">Standouts</h2><div className="salelist">{std.map((s) => <SaleTile key={s.id} s={s} go={go} onAct={(p) => sAct(s, p)} />)}</div></>}
      {rest.length > 0 && <><h2 className="sec">Everything else</h2><div className="salelist">{rest.map((s) => <SaleTile key={s.id} s={s} go={go} onAct={(p) => sAct(s, p)} />)}</div></>}
    </>
  );
}

function SaleView({ id, go, toast }: { id: string; go: (p: string) => void; toast: (m: string) => void }) {
  const [sale, setSale] = useState<Sale | null>(null);
  const [hits, setHits] = useState<Hit[]>([]);
  const [missing, setMissing] = useState(false);
  useEffect(() => { get<{ sale: Sale; hits: Hit[] }>("sale/" + id).then((r) => {
    setSale(r.sale);
    setHits(r.hits.map((h) => ({ ...h, sale_name: r.sale.name, city: r.sale.city, sale_state: r.sale.state, address: r.sale.address, sale_url: r.sale.url, type_name: r.sale.type_name, start_date: r.sale.start_date, end_date: r.sale.end_date, sale_standout: r.sale.standout })));
  }).catch((e) => e.message !== "locked" && setMissing(true)); }, [id]);
  const setS = useCallback((f: (a: Sale[]) => Sale[]) => setSale((s) => (s ? f([s])[0] : s)), []);
  const sAct = useSaleActions(setS, toast);
  if (missing) return <div className="empty"><h3>Sale not found</h3><button className="lnk" onClick={() => go("/sales")}>Back to sales</button></div>;
  if (!sale) return <div className="empty">Loading</div>;
  let hours: { date: string; hours: string }[] = [];
  try { hours = sale.dates_json ? JSON.parse(sale.dates_json) : []; } catch { /* ignore */ }
  const pics = topPics(sale);
  return (
    <>
      <button className="back" onClick={() => history.length > 1 ? history.back() : go("/sales")}>&lsaquo; Back</button>
      <header className={"salehead" + (sale.standout ? " standout" : "")}>
        {sale.standout ? <span className="star inline">Standout sale</span> : null}
        <h1>{sale.name}</h1>
        <p className="sub">{sale.org}</p>
        <p className="sub strong">{dateRange(sale.start_date, sale.end_date)}{isOnline(sale.type_name) ? ", online auction" : ""}</p>
        <p className="sub">{[sale.address, sale.city, sale.state].filter(Boolean).join(", ")}</p>
        {sale.why ? <p className="why">{sale.why}</p> : null}
        {hours.length > 0 && <ul className="hours">{hours.map((h, i) => <li key={i}><b>{h.date}</b> {h.hours}</li>)}</ul>}
        <div className="links">
          {sale.url ? <a className="lnk" href={sale.url} target="_blank" rel="noreferrer">Open sale page</a> : null}
          <a className="lnk" href={mapLink(sale)} target="_blank" rel="noreferrer">Show on OpenStreetMap</a>
        </div>
        <SaleActs s={sale} onAct={(p) => sAct(sale, p)} />
      </header>
      {hits.length > 0 && <><h2 className="sec">Finds from this sale</h2>
        <HitGrid items={hits} setItems={setHits} toast={toast} showSale={false} onSale={() => {}} emptyMsg="" /></>}
      {pics.length > 0 && <><h2 className="sec">Top photos by luxe score</h2>
        <div className="toppics">{pics.map((p, i) => <a key={i} href={p.url || p.thumb} target="_blank" rel="noreferrer"><img src={p.thumb} alt="" loading="lazy" /></a>)}</div></>}
      {!hits.length && !pics.length && <div className="empty"><p>No flagged photos for this sale.</p></div>}
    </>
  );
}

function SavedView({ go, toast }: { go: (p: string) => void; toast: (m: string) => void }) {
  const [items, setItems] = useState<Hit[]>([]);
  const [sales, setSales] = useState<Sale[]>([]);
  const [loading, setLoading] = useState(true);
  const sAct = useSaleActions(setSales, toast);
  useEffect(() => {
    Promise.all([get<{ items: Hit[] }>("feed", { saved: 1, hidden: 1, limit: 200 }), get<{ items: Sale[] }>("sales", { saved: 1 })])
      .then(([a, b]) => { setItems(a.items); setSales(b.items); }).catch(() => {}).finally(() => setLoading(false));
  }, []);
  return (
    <>
      <div className="filters"><h1 className="pg">Saved</h1></div>
      {!loading && !items.length && !sales.length && <div className="empty"><h3>Nothing saved</h3><p>Tap the bookmark on any find or sale you want to go see.</p></div>}
      {sales.length > 0 && <><h2 className="sec">Sales to visit</h2><div className="salelist">{sales.map((s) => <SaleTile key={s.id} s={s} go={go} onAct={(p) => sAct(s, p)} />)}</div></>}
      {items.length > 0 && <><h2 className="sec">Finds to see</h2><HitGrid items={items} setItems={setItems} toast={toast} onSale={(id) => go("/sales/" + id)} emptyMsg="" /></>}
    </>
  );
}

function needText(s: CatStat, t: Stats["threshold"]) {
  if (s.active) return "Learning. Low scoring finds in this group are now hidden.";
  const nu = Math.max(0, t.each_sign - s.up), nd = Math.max(0, t.each_sign - s.down);
  const rest = Math.max(0, t.labeled - s.labeled - nu - nd);
  const parts = [nu && `${nu} more loved`, nd && `${nd} more passed`, rest && `${rest} of either kind`].filter(Boolean);
  return "Needs " + parts.join(", ");
}
function TasteView() {
  const [st, setSt] = useState<Stats | null>(null);
  useEffect(() => { get<Stats>("stats").then(setSt).catch(() => {}); }, []);
  if (!st) return <div className="empty">Loading</div>;
  const t = st.threshold;
  const card = (s: CatStat, label: string, color: string, glyph: string) => {
    const eff = Math.min(s.up, t.each_sign) + Math.min(s.down, t.each_sign) + Math.min(Math.max(0, s.labeled - Math.min(s.up, t.each_sign) - Math.min(s.down, t.each_sign)), t.labeled - 2 * t.each_sign);
    const frac = Math.min(1, eff / t.labeled);
    return (
      <article className={"taste" + (s.active ? " active" : "")} key={label}>
        <Wheel lit={s.active ? 8 : Math.floor(frac * 8)} active={s.active} color={color} />
        <div>
          <h3><CatGlyph cat={glyph} size={18} /> {label}</h3>
          <p className="big">{Math.min(s.labeled, 999)} <small>of {t.labeled} votes</small></p>
          <p className="sub">{s.up} loved, {s.down} passed, {s.saved} saved</p>
          <p className="need">{needText(s, t)}</p>
          {s.total ? <p className="sub">{s.total} finds scanned, {s.hidden} hidden</p> : null}
        </div>
      </article>
    );
  };
  return (
    <>
      <div className="filters"><h1 className="pg">Taste</h1></div>
      <p className="lede">Each wheel turns on after {t.labeled} votes with at least {t.each_sign} loved and {t.each_sign} passed. Then the scanner starts hiding finds you would likely pass.</p>
      <div className="tastegrid">
        {st.categories.map((c) => card(c, catMeta(c.category).label, catMeta(c.category).color, c.category))}
        {card(st.sales, "Standout sales", "#C9D6C9", "sales")}
      </div>
      <p className="sub foot">{st.totals.hits} finds and {st.totals.sales} sales scanned, {st.totals.standouts} standouts.</p>
    </>
  );
}

function Locked() {
  return (
    <main className="locked">
      <Fan />
      <h1>Locked</h1>
      <p>Open the app from the link in your daily email.</p>
    </main>
  );
}

/* ---------- shell ---------- */
const TABS = [["/", "Finds"], ["/sales", "Sales"], ["/saved", "Saved"], ["/taste", "Taste"]] as const;

export default function App() {
  const [path, go] = usePath();
  const [msg, toast] = useToast();
  const locked = useLocked();
  useEffect(() => {
    const v = new URLSearchParams(location.search).get("voted");
    if (v) { toast(v.endsWith(":1") ? "Vote saved: loved" : "Vote saved: passed"); history.replaceState({}, "", location.pathname); }
  }, [toast]);
  const m = /^\/sales\/(\d+)/.exec(path);
  const active = path === "/" ? "/" : "/" + path.split("/")[1];
  const view = useMemo(() => {
    if (m) return <SaleView key={m[1]} id={m[1]} go={go} toast={toast} />;
    if (path === "/sales") return <SalesView go={go} toast={toast} />;
    if (path === "/saved") return <SavedView key="saved" go={go} toast={toast} />;
    if (path === "/taste") return <TasteView />;
    return <FeedView toast={toast} go={go} />;
  }, [path]); // eslint-disable-line
  if (locked) return <Locked />;
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="mast">
        <Fan />
        <div className="mast-in">
          <a className="word" href="/" onClick={(e) => { e.preventDefault(); go("/"); }}>Estate Sale Watch<small>Front Range finds</small></a>
          <nav className="tabs" aria-label="Main">
            {TABS.map(([to, l]) => <a key={to} href={to} className={active === to ? "on" : ""} aria-current={active === to ? "page" : undefined} onClick={(e) => { e.preventDefault(); go(to); }}>{l}</a>)}
          </nav>
        </div>
      </header>
      <main id="main" className="page">{view}</main>
      <div className={"toast" + (msg ? " show" : "")} role="status" aria-live="polite">{msg}</div>
    </>
  );
}
