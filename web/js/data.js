// 저장소의 JSON만 읽는다. 브라우저는 API를 직접 호출하지 않는다.
const DEFAULT_BASE = "data/";

async function fetchJson(url) {
  const res = await fetch(`${url}?v=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

export async function loadAll(base = DEFAULT_BASE) {
  try {
    const [notices, awards, meta, plans] = await Promise.all([
      fetchJson(`${base}notices.json`),
      fetchJson(`${base}awards.json`),
      fetchJson(`${base}meta.json`),
      fetchJson(`${base}plans.json`).catch(() => ({ items: [] })), // 발주계획 수집 전 배포본에는 파일이 없다
    ]);
    return { notices: notices.items ?? [], awards: awards.items ?? [], plans: plans.items ?? [], meta };
  } catch (err) {
    return { notices: [], awards: [], plans: [], meta: { ok: false, run_at: null, errors: [`데이터 로드 실패: ${err.message}`] } };
  }
}
