// 캘린더 뷰: 월 그리드 + 선택일 이벤트 목록.
import { buildMonthGrid, shiftMonth, toEvents } from "../lib/calendar.js";
import { el, esc } from "../lib/dom.js";
import { applyFilters } from "../lib/filter.js";
import { localDateKey, formatDateTime, trackLabel } from "../lib/format.js";
import { noticeTable } from "../lib/rows.js";

const DOW = ["일", "월", "화", "수", "목", "금", "토"];
const MAX_CHIPS = 3;
let view = { year: null, month: null, selected: null };

function eventChip(e) {
  const label = `${e.type === "close" ? "마감" : "개찰"} ${esc(e.notice.title)}`;
  return `<div class="ev ${esc(e.notice.track)} ${e.type} ${e.notice.interest ? "interest" : ""}" title="${label}">${label}</div>`;
}

function eventDot(e) {
  return `<span class="ev-dot ${esc(e.notice.track)} ${e.notice.interest ? "interest" : ""}"></span>`;
}

function cellNode(cell, today, onPick) {
  const classes = ["cal-cell", cell.inMonth ? "" : "out", cell.date === today ? "today" : "",
    cell.date === view.selected ? "selected" : ""].join(" ");
  const chips = cell.events.slice(0, MAX_CHIPS).map(eventChip).join("");
  const more = cell.events.length > MAX_CHIPS ? `<div class="ev-more">+${cell.events.length - MAX_CHIPS}</div>` : "";
  const node = el("div", { class: classes, onclick: () => onPick(cell.date) });
  node.innerHTML = `<div class="d">${Number(cell.date.slice(-2))}</div>${chips}${more}<div class="ev-dots">${cell.events.map(eventDot).join("")}</div>`;
  return node;
}

function selectedList(events, state) {
  if (!view.selected) return el("div", { class: "empty" }, "날짜를 누르면 그날의 마감·개찰 목록이 표시됩니다.");
  const todays = events.filter((e) => e.date === view.selected);
  const items = todays.map((e) => ({ ...e.notice, _evt: e.type }));
  const title = `${view.selected} · 마감 ${todays.filter((e) => e.type === "close").length}건, 개찰 ${todays.filter((e) => e.type === "open").length}건`;
  return el("div", { class: "section cal-list" }, [
    el("h2", {}, title),
    noticeTable(items, { now: state.now, onSelect: state.select, emptyText: "이 날에는 마감·개찰 일정이 없습니다." }),
  ]);
}

export function render(container, state) {
  const now = state.now;
  if (!view.year) view = { ...view, year: now.getFullYear(), month: now.getMonth() + 1 };
  const scoped = applyFilters(state.notices, state.filters);
  const events = toEvents(scoped.filter((n) => !["cancelled"].includes(n.status)));
  const grid = buildMonthGrid(view.year, view.month, events);
  const today = localDateKey(now);
  const pick = (date) => { view = { ...view, selected: view.selected === date ? null : date }; render(container, state); };
  const move = (delta) => { view = { ...view, ...shiftMonth(view.year, view.month, delta), selected: null }; render(container, state); };

  const head = el("div", { class: "cal-head" }, [
    el("button", { type: "button", onclick: () => move(-1) }, "‹ 이전"),
    el("h2", {}, grid.label),
    el("div", {}, [
      el("button", { type: "button", onclick: () => { view = { ...view, year: now.getFullYear(), month: now.getMonth() + 1 }; render(container, state); } }, "오늘"),
      " ",
      el("button", { type: "button", onclick: () => move(1) }, "다음 ›"),
    ]),
  ]);
  const legend = el("div", { class: "legend", html:
    `<span><span class="sw" style="background:var(--c-public)"></span>${esc(trackLabel("public"))} 마감</span>
     <span><span class="sw" style="background:var(--c-public-soft)"></span>${esc(trackLabel("public"))} 개찰</span>
     <span><span class="sw" style="background:var(--c-apt)"></span>${esc(trackLabel("apt"))} 마감</span>
     <span><span class="sw" style="background:var(--c-apt-soft)"></span>${esc(trackLabel("apt"))} 개찰</span>
     <span><span class="sw" style="outline:2px solid var(--interest);outline-offset:-1px"></span>관심지역</span>` });
  const gridNode = el("div", { class: "cal-grid" }, [
    ...DOW.map((d) => el("div", { class: "cal-dow" }, d)),
    ...grid.weeks.flat().map((cell) => cellNode(cell, today, pick)),
  ]);
  container.replaceChildren(head, legend, gridNode, selectedList(events, state));
}
