// 대시보드: KPI 4개 → 관심지역 섹션(고정) → 진행중 공고.
import { el } from "../lib/dom.js";
import { ACTIVE_STATUSES, applyFilters, sortByClose } from "../lib/filter.js";
import { noticeTable } from "../lib/rows.js";
import { kpis } from "../lib/stats.js";

function kpiCard(label, value, extraClass = "") {
  return el("div", { class: `kpi ${extraClass}` }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, String(value)),
  ]);
}

function section(title, count, content, extraClass = "") {
  return el("div", { class: "section" }, [
    el("h2", {}, [title, el("span", { class: "count" }, `${count}건`)]),
    el("div", { class: extraClass }, content),
  ]);
}

export function render(container, state) {
  const { notices, awards, now, filters, select } = state;
  const scoped = applyFilters(notices, { track: filters.track, query: filters.query });
  const k = kpis(scoped, awards, now);
  const active = sortByClose(applyFilters(scoped, { interestOnly: filters.interestOnly, statuses: ACTIVE_STATUSES }));
  const interest = active.filter((n) => n.interest);

  container.replaceChildren(
    el("div", { class: "kpis" }, [
      kpiCard("오늘 신규", k.newToday),
      kpiCard("7일 내 마감", k.closingIn7),
      kpiCard("관심지역 진행중", k.interestOpen, "interest"),
      kpiCard("이번 주 개찰", k.openingThisWeek),
    ]),
    section("관심지역 공고 (전남광주·호남)", interest.length,
      noticeTable(interest, { now, onSelect: select, emptyText: "진행중인 관심지역 공고가 없습니다." }),
      "panel interest-panel"),
    section("진행중 공고 (마감 임박순)", active.length,
      noticeTable(active, { now, onSelect: select })),
  );
}
