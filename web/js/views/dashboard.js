// 대시보드: KPI → 관심지역(고정) → 주타겟 업무 진행중 → 기타 업무(접힘).
import { el } from "../lib/dom.js";
import { ACTIVE_STATUSES, applyFilters, categoryOf, sortByClose } from "../lib/filter.js";
import { noticeTable } from "../lib/rows.js";
import { kpis } from "../lib/stats.js";

function kpiCard(label, value, extraClass = "") {
  return el("div", { class: `kpi ${extraClass}` }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, [String(value), el("span", { class: "unit" }, "건")]),
  ]);
}

function section(title, count, content, extraClass = "") {
  return el("div", { class: "section" }, [
    el("h2", {}, [title, el("span", { class: "count" }, `${count}건`)]),
    el("div", { class: extraClass }, content),
  ]);
}

function collapsed(title, count, content) {
  const details = el("details", { class: "section collapsible" });
  details.append(el("summary", {}, [el("h2", {}, [title, el("span", { class: "count" }, `${count}건`)])]));
  details.append(content);
  return details;
}

// 공고중(마감 임박순) 먼저, 마감(개찰 대기)은 그 뒤
const activeOrder = (rows) => [...sortByClose(rows.filter((n) => n.status === "open")), ...sortByClose(rows.filter((n) => n.status !== "open"))];

export function render(container, state) {
  const { notices, awards, now, filters, select } = state;
  const scoped = applyFilters(notices, { track: filters.track, query: filters.query });
  const k = kpis(scoped, awards, now);
  const visible = applyFilters(scoped, { category: filters.category, interestOnly: filters.interestOnly, statuses: ACTIVE_STATUSES });
  const active = activeOrder(visible);
  const interest = active.filter((n) => n.interest);
  const target = active.filter((n) => categoryOf(n) === "target");
  const other = active.filter((n) => categoryOf(n) === "other");
  const opts = { now, onSelect: select };

  const blocks = [
    el("div", { class: "kpis card" }, [
      kpiCard("오늘 신규", k.newToday),
      kpiCard("주타겟 진행중", k.targetOpen, "target"),
      kpiCard("관심지역 진행중", k.interestOpen, "interest"),
      kpiCard("7일 내 마감", k.closingIn7),
      kpiCard("이번 주 개찰", k.openingThisWeek),
    ]),
    section("관심지역 공고 (전남광주·호남)", interest.length,
      noticeTable(interest, { ...opts, emptyText: "진행중인 관심지역 공고가 없습니다." }), "panel interest-panel"),
  ];
  if (filters.category !== "other") {
    blocks.push(section("주타겟 업무 진행중 (마감 임박순)", target.length,
      noticeTable(target, { ...opts, emptyText: "진행중인 주타겟 업무 공고가 없습니다." })));
  }
  if (filters.category !== "target") {
    const table = noticeTable(other, { ...opts, emptyText: "진행중인 기타 업무 공고가 없습니다." });
    blocks.push(filters.category === "other" ? section("기타 업무 진행중 (마감 임박순)", other.length, table)
      : collapsed("기타 업무 진행중 (펼치기)", other.length, table));
  }
  container.replaceChildren(...blocks);
}
