// 월 그리드 생성 (순수 함수). 주는 일요일 시작, 6주 42셀 고정.
import { localDateKey, toDateKey } from "./format.js";

export function toEvents(notices) {
  return notices.flatMap((notice) => {
    const out = [];
    const close = toDateKey(notice.close_at);
    const open = toDateKey(notice.open_at);
    if (close) out.push({ date: close, type: "close", notice });
    if (open) out.push({ date: open, type: "open", notice });
    return out;
  });
}

export function shiftMonth(year, month, delta) {
  const d = new Date(year, month - 1 + delta, 1);
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

export function buildMonthGrid(year, month, events) {
  const first = new Date(year, month - 1, 1);
  const start = new Date(year, month - 1, 1 - first.getDay());
  const byDate = events.reduce((acc, e) => ({ ...acc, [e.date]: [...(acc[e.date] ?? []), e] }), {});
  const cells = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    const date = localDateKey(d);
    return { date, inMonth: d.getMonth() === month - 1, events: byDate[date] ?? [] };
  });
  const weeks = Array.from({ length: 6 }, (_, w) => cells.slice(w * 7, w * 7 + 7));
  return { weeks, label: `${year}년 ${month}월` };
}
