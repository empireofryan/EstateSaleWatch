"""estatesales.net HTTP helpers (plain requests, browser UA, retries, small concurrency)."""
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BASE = "https://www.estatesales.net"
LIST_URL = (BASE + "/api/sale-details?bypass=bycoordinatesanddistance:{lat}_{lon}_{mi}"
            "&include=saleschedule&select=id,cityName,stateCode,postalCodeNumber,latitude,longitude,"
            "type,firstLocalStartDate,lastLocalEndDate,utcDateFirstPublished,saleSchedule"
            "&explicitTypes=DateTime")
DETAIL_URL = (BASE + "/api/legacy/queries/traditional-sales/traditional-sale?query={q}"
              "&explicitTypes=DateTime")

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept": "application/json,image/*,*/*"})


def get(url, retries=4, timeout=30, **kw):
    """GET with exponential backoff. Returns Response or raises the last error."""
    last = None
    for i in range(retries):
        try:
            r = _session.get(url, timeout=timeout, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(1.5 * 2 ** i)
    raise last


def dt(v):
    """{'_type':'DateTime','_value':'2026-10-02T00:00:00Z'} -> datetime (naive, local-as-written)."""
    if isinstance(v, dict):
        v = v.get("_value")
    if not v:
        return None
    return datetime.strptime(v[:19], "%Y-%m-%dT%H:%M:%S")


def fetch_list(lat, lon, miles):
    r = get(LIST_URL.format(lat=lat, lon=lon, mi=miles))
    r.raise_for_status()
    return r.json()


def fetch_detail(sale_id):
    q = urllib.parse.quote(json.dumps({"saleId": sale_id, "userId": None, "isSuper": False},
                                      separators=(",", ":")))
    r = get(DETAIL_URL.format(q=q))
    if r.status_code != 200:
        return None
    try:
        return r.json().get("sale")
    except ValueError:
        return None


def _fmt_t(d):
    s = d.strftime("%I:%M%p").lstrip("0").lower().replace(":00", "")
    return s


def normalize(sale, list_row=None):
    """Reduce a raw sale detail to the compact meta we store/render."""
    li = sale.get("locationInfo") or {}
    addr = (li.get("address") or {})
    pc = addr.get("postalCode") or {}
    city = pc.get("cityName") or sale.get("postalCodeCityName") or (list_row or {}).get("cityName", "")
    zipc = pc.get("postalCodeNumber") or (list_row or {}).get("postalCodeNumber", "")
    street = addr.get("addressLine1") if li.get("showAddress", True) else ""
    hours = []
    for d in sale.get("dates") or []:
        s, e = dt(d.get("localStartDate")), dt(d.get("localEndDate"))
        if not s:
            continue
        txt = s.strftime("%a %b %d").replace(" 0", " ") + " " + _fmt_t(s)
        if e and d.get("showEndTime", True):
            txt += "-" + _fmt_t(e)
        hours.append(txt)
    path = sale.get("url") or ""
    return {
        "id": sale.get("saleId"),
        "name": sale.get("name") or "",
        "org": (sale.get("seller") or {}).get("name", ""),
        "type": sale.get("type"),
        "typeName": sale.get("typeName"),
        "online": sale.get("type") == 64,
        "city": city, "zip": zipc,
        "address": (street or "").strip(),
        "start": (dt(sale.get("firstLocalStartDate")) or datetime.min).strftime("%Y-%m-%d"),
        "end": (dt(sale.get("lastLocalEndDate")) or datetime.max.replace(year=9999)).strftime("%Y-%m-%d"),
        "hours": hours,
        "page": BASE + path if path else f"{BASE}/CO/{city.replace(' ', '-')}/{zipc}/{sale.get('saleId')}",
        "text": (sale.get("plainTextDescription") or "")[:4000],
    }


def pictures(sale):
    out = []
    for p in sale.get("pictures") or []:
        if p.get("id") and p.get("thumbnailUrl"):
            out.append({"id": p["id"], "order": p.get("pictureOrder"), "url": p.get("url"),
                        "thumb": p["thumbnailUrl"], "caption": p.get("description") or ""})
    return out


def map_pool(fn, items, workers=6):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))
