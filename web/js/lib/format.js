// 표시용 순수 함수: 금액·날짜·D-day·라벨.

const STATUS_LABELS = Object.freeze({
  open: "공고중", closed: "마감", opened: "개찰완료", awarded: "낙찰", failed: "유찰",
  rebid: "재입찰", cancelled: "취소", unknown: "결과미확인",
});
const TRACK_LABELS = Object.freeze({ public: "공공기관", apt: "아파트" });
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const DAY_MS = 86_400_000;

export function parseIso(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

function trimNumber(n, digits) {
  return Number(n.toFixed(digits)).toLocaleString("ko-KR");
}

export function formatAmount(n) {
  if (!n || n <= 0) return "-";
  if (n >= 100_000_000) return `${trimNumber(n / 100_000_000, 1)}억원`;
  return `${trimNumber(n / 10_000, 1)}만원`;
}

export function formatDate(iso) {
  const d = parseIso(iso);
  if (!d) return "-";
  return `${d.getMonth() + 1}/${String(d.getDate()).padStart(2, "0")}(${WEEKDAYS[d.getDay()]})`;
}

export function formatDateTime(iso) {
  const d = parseIso(iso);
  if (!d) return "-";
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${d.getMonth() + 1}/${String(d.getDate()).padStart(2, "0")} ${hh}:${mm}`;
}

function startOfDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function dday(iso, now = new Date()) {
  const d = parseIso(iso);
  if (!d) return null;
  return Math.round((startOfDay(d) - startOfDay(now)) / DAY_MS);
}

export function ddayLabel(iso, now = new Date()) {
  const n = dday(iso, now);
  if (n === null) return "-";
  if (n === 0) return "오늘";
  return n > 0 ? `D-${n}` : "마감";
}

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? status;
}

export function trackLabel(track) {
  return TRACK_LABELS[track] ?? track;
}

export function regionLabel(region) {
  return region || "미분류";
}

export function localDateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function toDateKey(iso) {
  const d = parseIso(iso);
  return d ? localDateKey(d) : null;
}
