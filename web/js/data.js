// 저장소의 JSON만 읽는다. 브라우저는 API를 직접 호출하지 않는다.
const DEFAULT_BASE = "data/";

async function fetchJson(url) {
  const res = await fetch(`${url}?v=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

export async function loadAll(base = DEFAULT_BASE) {
  try {
    const [notices, awards, meta] = await Promise.all([
      fetchJson(`${base}notices.json`),
      fetchJson(`${base}awards.json`),
      fetchJson(`${base}meta.json`),
    ]);
    return { notices: notices.items ?? [], awards: awards.items ?? [], meta };
  } catch (err) {
    return { notices: [], awards: [], meta: { ok: false, run_at: null, errors: [`데이터 로드 실패: ${err.message}`] } };
  }
}
