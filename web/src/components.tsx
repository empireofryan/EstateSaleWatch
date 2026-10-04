import { useEffect, useRef, useState } from "react";
import { CatGlyph, IconDown, IconSave, IconUp } from "./Glyphs";
import { catMeta, dateRange, isOnline, mapLink, postVote, type Hit, type Sale } from "./api";

export type Patch = { vote?: 1 | -1 | null; saved?: number };

export function Plate({ it, selected, dim, showSale = true, onOpen, onAct, idx }: {
  it: Hit; selected?: boolean; dim?: boolean; showSale?: boolean; idx: number;
  onOpen: () => void; onAct: (p: Patch) => void;
}) {
  const m = catMeta(it.category);
  const when = dateRange(it.start_date, it.end_date);
  return (
    <article className={"plate" + (selected ? " sel" : "") + (dim ? " dim" : "") + (it.hidden ? " hid" : "")} data-idx={idx}>
      <div className="frame"><div className="inner">
        <button className="photo" onClick={onOpen} aria-label={`Open ${m.label} find${it.sale_name ? " from " + it.sale_name : ""}`}>
          <img src={it.thumb} alt={it.caption || `${m.label} find`} loading="lazy" decoding="async" />
          <span className="badge" style={{ ["--c" as string]: m.color }}><CatGlyph cat={it.category} size={15} />{m.label}</span>
          {it.sale_standout ? <span className="star" title="Standout sale">Standout</span> : null}
          {it.hidden ? <span className="hidden-tag">Hidden by taste</span> : null}
        </button>
        {showSale && (
          <div className="meta">
            <b>{it.sale_name || "Sale " + it.sale_id}</b>
            <span>{[it.city, when].filter(Boolean).join(", ")}</span>
          </div>
        )}
        <div className="acts">
          <button className={"act dn" + (it.vote === -1 ? " on" : "")} aria-pressed={it.vote === -1} aria-label="Thumbs down" onClick={() => onAct({ vote: it.vote === -1 ? null : -1 })}><IconDown on={it.vote === -1} /></button>
          <button className={"act sv" + (it.saved ? " on" : "")} aria-pressed={!!it.saved} aria-label={it.saved ? "Remove from saved" : "Save to go see"} onClick={() => onAct({ saved: it.saved ? 0 : 1 })}><IconSave on={!!it.saved} /></button>
          <button className={"act up" + (it.vote === 1 ? " on" : "")} aria-pressed={it.vote === 1} aria-label="Thumbs up" onClick={() => onAct({ vote: it.vote === 1 ? null : 1 })}><IconUp on={it.vote === 1} /></button>
        </div>
      </div></div>
    </article>
  );
}

export function SaleActs({ s, onAct }: { s: Sale; onAct: (p: Patch) => void }) {
  return (
    <div className="sale-acts">
      <button className={"act dn" + (s.vote === -1 ? " on" : "")} aria-pressed={s.vote === -1} aria-label="Thumbs down this sale" onClick={() => onAct({ vote: s.vote === -1 ? null : -1 })}><IconDown on={s.vote === -1} /></button>
      <button className={"act sv" + (s.saved ? " on" : "")} aria-pressed={!!s.saved} aria-label={s.saved ? "Remove sale from saved" : "Save sale"} onClick={() => onAct({ saved: s.saved ? 0 : 1 })}><IconSave on={!!s.saved} /></button>
      <button className={"act up" + (s.vote === 1 ? " on" : "")} aria-pressed={s.vote === 1} aria-label="Thumbs up this sale" onClick={() => onAct({ vote: s.vote === 1 ? null : 1 })}><IconUp on={s.vote === 1} /></button>
    </div>
  );
}

export interface TopPic { pic_id?: string; thumb: string; url?: string; p?: number }
export const topPics = (s: { top_json: string | null }): TopPic[] => {
  try { return s.top_json ? JSON.parse(s.top_json) : []; } catch { return []; }
};

export function Lightbox({ it, onClose, onAct, onStep, onSale }: {
  it: Hit; onClose: () => void; onAct: (p: Patch) => void; onStep: (d: number) => void; onSale: (id: number) => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => { setLoaded(false); }, [it.pic_id]);
  useEffect(() => {
    closeRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);
  const m = catMeta(it.category);
  return (
    <div className="lb" role="dialog" aria-modal="true" aria-label="Find details" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="lb-card">
        <div className="lb-img">
          {!loaded && <img className="lb-thumb" src={it.thumb} alt="" />}
          <img className={"lb-full" + (loaded ? " ready" : "")} src={it.url} alt={it.caption || `${m.label} find`} onLoad={() => setLoaded(true)} />
          <button className="lb-nav prev" aria-label="Previous find" onClick={() => onStep(-1)}>&lsaquo;</button>
          <button className="lb-nav next" aria-label="Next find" onClick={() => onStep(1)}>&rsaquo;</button>
        </div>
        <div className="lb-side">
          <button ref={closeRef} className="lb-close" onClick={onClose} aria-label="Close">Close</button>
          <span className="badge flat" style={{ ["--c" as string]: m.color }}><CatGlyph cat={it.category} size={16} />{m.label}{it.score != null ? `, score ${it.score.toFixed(2)}` : ""}</span>
          <h2>{it.sale_name || "Sale " + it.sale_id}</h2>
          <p className="sub">{[it.address, it.city, it.sale_state].filter(Boolean).join(", ")}</p>
          <p className="sub strong">{dateRange(it.start_date, it.end_date)}{isOnline(it.type_name) ? ", online auction" : ""}</p>
          {it.caption ? <p className="cap">{it.caption}</p> : null}
          {it.why ? <p className="why">{it.why}</p> : null}
          <div className="acts big">
            <button className={"act dn" + (it.vote === -1 ? " on" : "")} aria-pressed={it.vote === -1} onClick={() => onAct({ vote: it.vote === -1 ? null : -1 })}><IconDown on={it.vote === -1} /><span>Pass</span></button>
            <button className={"act sv" + (it.saved ? " on" : "")} aria-pressed={!!it.saved} onClick={() => onAct({ saved: it.saved ? 0 : 1 })}><IconSave on={!!it.saved} /><span>{it.saved ? "Saved" : "Save"}</span></button>
            <button className={"act up" + (it.vote === 1 ? " on" : "")} aria-pressed={it.vote === 1} onClick={() => onAct({ vote: it.vote === 1 ? null : 1 })}><IconUp on={it.vote === 1} /><span>Love</span></button>
          </div>
          <div className="links">
            <button className="lnk" onClick={() => onSale(it.sale_id)}>See all finds from this sale</button>
            {it.sale_url ? <a className="lnk" href={it.sale_url} target="_blank" rel="noreferrer">Open sale page</a> : null}
            <a className="lnk" href={mapLink(it)} target="_blank" rel="noreferrer">Show on OpenStreetMap</a>
          </div>
          <p className="keys" aria-hidden>j / k browse, u love, d pass, s save, esc close</p>
        </div>
      </div>
    </div>
  );
}

export { postVote };
