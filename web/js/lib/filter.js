// 공통 필터(트랙·관심지역·검색·상태)와 정렬. 입력을 바꾸지 않고 새 배열을 돌려준다.

const compact = (s) => String(s ?? "").replace(/\s+/g, "");

function matchesQuery(notice, query) {
  const q = compact(query);
  if (!q) return true;
  const haystack = [notice.title, notice.agency, notice.demand_agency, notice.complex_name]
    .map(compact).join("\u0000");
  return haystack.includes(q);
}

export function applyFilters(notices, { track = "all", interestOnly = false, query = "", statuses } = {}) {
  return notices.filter((n) =>
    (track === "all" || n.track === track)
    && (!interestOnly || n.interest)
    && (!statuses || statuses.includes(n.status))
    && matchesQuery(n, query));
}

export function sortByClose(notices) {
  return [...notices].sort((a, b) => {
    if (!a.close_at && !b.close_at) return 0;
    if (!a.close_at) return 1;
    if (!b.close_at) return -1;
    return a.close_at < b.close_at ? -1 : a.close_at > b.close_at ? 1 : 0;
  });
}

export const ACTIVE_STATUSES = Object.freeze(["open", "closed"]);
export const RESULT_STATUSES = Object.freeze(["opened", "awarded", "failed", "rebid", "unknown", "cancelled"]);
