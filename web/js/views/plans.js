// 발주계획 뷰: 입찰공고 전 단계인 나라장터 용역 발주계획. 발주 예정 / 예정월 경과 / 공고됨을 구역으로 나눠 보여준다.
import { toCsv } from "../lib/csv.js";
import { el, esc } from "../lib/dom.js";
import { categoryLabel, formatAmount, regionLabel, serviceLabel } from "../lib/format.js";
import { PLAN_STATUS_LABELS, RECENT_DAYS, filterPlans, groupByStatus, isRecentPlan, linkedNotices, orderMonthLabel, planStatus, planSummary, resetStaleFilters, sortPlans } from "../lib/plans.js";
import { interestChip, serviceChip } from "../lib/rows.js";
import { openPlanDetail } from "./detail.js";

let local = { status: "pending", month: "all", region: "all", method: "all" };

const STATUS_OPTIONS = [["pending", "공고 전 전체"], ["planned", "발주 예정만"], ["overdue", "예정월 경과만"], ["noticed", "공고됨"], ["all", "상태 전체"]];
// 화면에 나오는 구역 순서와 제목·설명
const SECTIONS = [
  ["planned", "발주 예정 (다가오는 발주월 순)", "입찰공고 전 단계의 계획입니다. 금액·시기·계약방법은 발주기관 사정으로 바뀔 수 있습니다."],
  ["overdue", "예정월 경과 · 공고 없음 (최근 달부터)", "발주 예정월이 지났는데 연결된 입찰공고가 없는 계획입니다. 발주가 늦어졌거나 입찰공고 없이 진행됐을 수 있습니다."],
  ["noticed", "공고된 계획", "이미 입찰공고가 나간 계획입니다. 행을 누르면 연결된 공고를 볼 수 있습니다."],
];
const CSV_COLUMNS = [
  { key: "month", label: "발주예정월" }, { key: "category", label: "구분" }, { key: "service", label: "업무" },
  { key: "title", label: "사업명" }, { key: "agency", label: "발주기관" }, { key: "parent", label: "총괄기관" },
  { key: "agencyType", label: "기관유형" }, { key: "region", label: "지역" }, { key: "amount", label: "예정금액" },
  { key: "method", label: "계약방법" }, { key: "procurement", label: "조달방식" }, { key: "dept", label: "담당부서" },
  { key: "tel", label: "전화" }, { key: "posted", label: "게시일" }, { key: "status", label: "상태" },
  { key: "notices", label: "입찰공고번호" }, { key: "url", label: "원문" },
];

function csvRows(plans, now) {
  return plans.map((p) => ({
    month: p.order_ym ?? "", category: categoryLabel(p.category), service: p.category === "target" ? serviceLabel(p.service) : "",
    title: p.title, agency: p.agency ?? "", parent: p.parent_agency ?? "", agencyType: p.agency_type ?? "",
    region: regionLabel(p.region), amount: p.amount ?? "", method: p.contract_method ?? "", procurement: p.procurement ?? "",
    dept: p.dept ?? "", tel: p.tel ?? "", posted: (p.posted_at ?? "").slice(0, 10),
    status: PLAN_STATUS_LABELS[planStatus(p, now)], notices: (p.notice_nos ?? []).join(" "), url: p.url ?? "",
  }));
}

function download(filename, text) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const a = el("a", { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a);
  a.click();
  a.remove();
}

function select(options, value, onchange, label) {
  const node = el("select", { "aria-label": label, onchange: (e) => onchange(e.target.value) });
  node.innerHTML = options.map(([v, text]) => `<option value="${esc(v)}" ${v === value ? "selected" : ""}>${esc(text)}</option>`).join("");
  return node;
}

// 선택지는 공통 필터만 적용한 목록에서 만든다(탭 전용 필터를 바꿔도 선택지가 사라지지 않도록).
function filtersBar(scoped, shown, now, rerender) {
  const set = (patch) => { local = { ...local, ...patch }; rerender(); };
  const months = [...new Set(scoped.map((p) => p.order_ym ?? "none"))].sort();
  const regions = [...new Set(scoped.map((p) => regionLabel(p.region)))].sort((a, b) => a.localeCompare(b, "ko"));
  const methods = [...new Set(scoped.map((p) => p.contract_method).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ko"));
  return el("div", { class: "award-filters" }, [
    select(STATUS_OPTIONS, local.status, (v) => set({ status: v }), "상태"),
    select([["all", "발주월 전체"], ...months.map((m) => [m, orderMonthLabel(m === "none" ? null : m)])], local.month, (v) => set({ month: v }), "발주 예정월"),
    select([["all", "지역 전체"], ...regions.map((r) => [r, r])], local.region, (v) => set({ region: v }), "지역"),
    select([["all", "계약방법 전체"], ...methods.map((m) => [m, m])], local.method, (v) => set({ method: v }), "계약방법"),
    el("button", { type: "button", class: "btn", onclick: () => download(`plans-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(csvRows(shown, now), CSV_COLUMNS)) }, "CSV 다운로드"),
  ]);
}

function kpi(label, value, unit, extraClass = "") {
  return el("div", { class: `kpi ${extraClass}` }, [
    el("div", { class: "label" }, label),
    el("div", { class: "value" }, [String(value), unit ? el("span", { class: "unit" }, unit) : null]),
  ]);
}

function summaryCards(shown, groups, now) {
  const s = planSummary(shown, now);
  return el("div", { class: "kpis card" }, [
    kpi("발주 예정", groups.planned.length, "건"),
    kpi("예정월 경과", groups.overdue.length, "건", "overdue"),
    kpi("주타겟 업무", s.target, "건", "target"),
    kpi("관심지역", s.interest, "건", "interest"),
    kpi(`최근 ${RECENT_DAYS}일 게시·변경`, s.recent, "건"),
  ]);
}

function sections(groups, now, onSelect) {
  const blocks = SECTIONS.filter(([status]) => groups[status].length).map(([status, title, note]) => {
    const rows = groups[status];
    const amount = formatAmount(planSummary(rows, now).amount);
    return el("div", { class: "section" }, [
      el("h2", {}, [title, el("span", { class: "count" }, `${rows.length}건${amount === "-" ? "" : ` · ${amount}`}`)]),
      el("p", { class: "muted plan-note" }, note),
      table(rows, now, onSelect),
    ]);
  });
  return blocks.length ? blocks : [el("div", { class: "empty" }, "조건에 맞는 발주계획이 없습니다.")];
}

function statusChip(status) {
  return `<span class="chip chip-status plan-${esc(status)}">${esc(PLAN_STATUS_LABELS[status])}</span>`;
}

function table(shown, now, onSelect) {
  const t = el("table", { class: "list" });
  t.innerHTML = `<thead><tr><th>발주예정</th><th>사업명</th><th>발주기관</th><th>지역</th><th class="num">예정금액</th><th>계약방법</th><th>담당부서</th><th>상태</th></tr></thead>`;
  const tbody = el("tbody");
  for (const p of shown) {
    const tr = el("tr", { class: p.interest ? "interest" : "", onclick: () => onSelect(p) });
    const recent = isRecentPlan(p, now) ? '<span class="chip chip-new">신규</span>' : "";
    const parent = p.parent_agency && p.parent_agency !== p.agency ? ` <span class="muted">(${esc(p.parent_agency)})</span>` : "";
    tr.innerHTML = `
      <td data-label="발주예정" class="nowrap">${esc(orderMonthLabel(p.order_ym))}</td>
      <td class="title-cell"><span class="chips">${serviceChip(p)}${interestChip(p)}${recent}</span><span class="title-text">${esc(p.title)}</span></td>
      <td data-label="발주기관">${esc(p.agency ?? "-")}${parent}</td>
      <td data-label="지역" class="nowrap">${esc(regionLabel(p.region))}</td>
      <td data-label="예정금액" class="num">${esc(formatAmount(p.amount))}</td>
      <td data-label="계약방법" class="nowrap">${esc(p.contract_method ?? "-")}</td>
      <td data-label="담당부서">${esc(p.dept ?? "-")}${p.tel ? ` <span class="muted plan-tel">${esc(p.tel)}</span>` : ""}</td>
      <td data-label="상태">${statusChip(planStatus(p, now))}</td>`;
    tbody.append(tr);
  }
  t.append(tbody);
  return t;
}

export function render(container, state) {
  const { plans = [], notices, filters, now, select: openNotice } = state;
  if (filters.track === "apt") {
    container.replaceChildren(el("div", { class: "empty" }, "발주계획은 공공기관(나라장터)만 제공됩니다. 트랙을 '전체' 또는 '공공기관'으로 바꿔 주세요."));
    return;
  }
  const scoped = filterPlans(plans, filters, { status: "all" }, now);
  local = resetStaleFilters(local, scoped);
  const shown = sortPlans(filterPlans(plans, filters, local, now), now);
  const noticeByNo = new Map(notices.filter((n) => n.track === "public").map((n) => [n.notice_no, n]));
  const onSelect = (plan) => openPlanDetail(plan, {
    status: PLAN_STATUS_LABELS[planStatus(plan, now)], posted: (plan.posted_at ?? "-").slice(0, 10),
    linked: linkedNotices(plan, noticeByNo), onOpenNotice: openNotice,
  });
  const groups = groupByStatus(shown, now);
  container.replaceChildren(
    filtersBar(scoped, shown, now, () => render(container, state)),
    summaryCards(shown, groups, now),
    ...sections(groups, now, onSelect),
  );
}
