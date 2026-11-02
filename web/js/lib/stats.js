// KPI·지역 집계·낙찰 요약·수집 상태 배지. 모두 순수 함수.
import { dday, localDateKey, parseIso } from "./format.js";
import { ACTIVE_STATUSES } from "./filter.js";

const STALE_HOURS = 36;

const isActive = (n) => ACTIVE_STATUSES.includes(n.status);

export function kpis(notices, awards, now = new Date()) {
  const today = localDateKey(now);
  const within = (iso, min, max) => {
    const d = dday(iso, now);
    return d !== null && d >= min && d <= max;
  };
  return {
    newToday: notices.filter((n) => n.first_seen === today).length,
    closingIn7: notices.filter((n) => isActive(n) && within(n.close_at, 0, 7)).length,
    interestOpen: notices.filter((n) => isActive(n) && n.interest).length,
    openingThisWeek: notices.filter((n) => isActive(n) && within(n.open_at, 0, 7)).length,
  };
}

export function countByRegion(notices) {
  return notices.filter(isActive).reduce((acc, n) => {
    const key = n.region || "미분류";
    return { ...acc, [key]: (acc[key] ?? 0) + 1 };
  }, {});
}

export function awardSummary(awards) {
  if (!awards.length) return { count: 0, avgRate: null, topWinners: [] };
  const rates = awards.map((a) => a.rate).filter((r) => typeof r === "number");
  const avgRate = rates.length ? Number((rates.reduce((s, r) => s + r, 0) / rates.length).toFixed(1)) : null;
  const counts = awards.reduce((acc, a) => (a.winner ? { ...acc, [a.winner]: (acc[a.winner] ?? 0) + 1 } : acc), {});
  const topWinners = Object.entries(counts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "ko"))
    .slice(0, 5);
  return { count: awards.length, avgRate, topWinners };
}

export function statusBadgeClass(meta, now = new Date()) {
  if (!meta || !meta.ok) return "fail";
  const ran = parseIso(meta.run_at);
  if (!ran) return "fail";
  return (now - ran) / 3_600_000 > STALE_HOURS ? "stale" : "ok";
}
