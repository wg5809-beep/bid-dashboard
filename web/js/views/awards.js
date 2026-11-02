// 낙찰 축적 뷰: 결과가 난 공고(낙찰·유찰·재입찰·결과미확인·취소) + 필터 + 요약 + CSV.
import { toCsv } from "../lib/csv.js";
import { el, esc } from "../lib/dom.js";
import { RESULT_STATUSES, applyFilters } from "../lib/filter.js";
import { categoryLabel, formatAmount, formatDate, formatDateTime, regionLabel, serviceLabel, statusLabel, toDateKey } from "../lib/format.js";
import { interestChip, serviceChip, statusChip, trackChip } from "../lib/rows.js";
import { awardSummary } from "../lib/stats.js";

let local = { from: "", to: "", status: "all", region: "all", winner: "" };

const CSV_COLUMNS = [
  { key: "opened", label: "개찰일" }, { key: "track", label: "트랙" }, { key: "category", label: "구분" }, { key: "service", label: "업무" }, { key: "title", label: "공고명" },
  { key: "agency", label: "기관" }, { key: "region", label: "지역" }, { key: "budget", label: "기초금액" },
  { key: "winner", label: "낙찰자" }, { key: "amount", label: "낙찰금액" }, { key: "rate", label: "낙찰률" },
  { key: "participants", label: "참가업체수" }, { key: "status", label: "상태" }, { key: "url", label: "원문" },
];

function joinRows(notices, awardByKey) {
  return notices.map((n) => {
    const a = awardByKey.get(n.key);
    return {
      notice: n, award: a,
      opened: toDateKey(a?.opened_at ?? n.open_at ?? n.close_at) ?? "",
      track: n.track === "apt" ? "아파트" : "공공기관",
      category: categoryLabel(n.category), service: n.category === "target" ? serviceLabel(n.service) : "",
      title: n.title, agency: n.agency ?? "", region: regionLabel(n.region), budget: n.budget ?? n.estimate ?? "",
      winner: a?.winner ?? "", amount: a?.amount ?? "", rate: a?.rate ?? "", participants: a?.participants ?? "",
      status: statusLabel(n.status), url: n.url ?? "",
    };
  });
}

function applyLocal(rows) {
  const compact = (s) => String(s ?? "").replace(/\s+/g, "");
  return rows.filter((r) =>
    (!local.from || r.opened >= local.from)
    && (!local.to || r.opened <= local.to)
    && (local.status === "all" || r.notice.status === local.status)
    && (local.region === "all" || r.region === local.region)
    && (!local.winner || compact(r.winner).includes(compact(local.winner))));
}

function download(filename, text) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const a = el("a", { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a);
  a.click();
  a.remove();
}

function filtersBar(rows, rerender) {
  const regions = [...new Set(rows.map((r) => r.region))].sort((a, b) => a.localeCompare(b, "ko"));
  const set = (patch) => { local = { ...local, ...patch }; rerender(); };
  const statusSel = el("select", { onchange: (e) => set({ status: e.target.value }) });
  statusSel.innerHTML = `<option value="all">상태 전체</option>${RESULT_STATUSES.map((s) => `<option value="${s}" ${local.status === s ? "selected" : ""}>${esc(statusLabel(s))}</option>`).join("")}`;
  const regionSel = el("select", { onchange: (e) => set({ region: e.target.value }) });
  regionSel.innerHTML = `<option value="all">지역 전체</option>${regions.map((r) => `<option value="${esc(r)}" ${local.region === r ? "selected" : ""}>${esc(r)}</option>`).join("")}`;
  return el("div", { class: "award-filters" }, [
    el("input", { type: "date", value: local.from, "aria-label": "시작일", onchange: (e) => set({ from: e.target.value }) }),
    "~",
    el("input", { type: "date", value: local.to, "aria-label": "종료일", onchange: (e) => set({ to: e.target.value }) }),
    statusSel, regionSel,
    el("input", { type: "search", placeholder: "낙찰자 검색", value: local.winner, oninput: (e) => set({ winner: e.target.value }) }),
    el("button", { type: "button", class: "btn", onclick: () => download(`awards-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(applyLocal(rows), CSV_COLUMNS)) }, "CSV 다운로드"),
  ]);
}

function summaryCards(rows) {
  const s = awardSummary(rows.map((r) => r.award).filter(Boolean));
  const top = s.topWinners.map((w) => `<li>${esc(w.name)} <span class="muted">${w.count}건</span></li>`).join("");
  return el("div", { class: "summary" }, [
    el("div", { class: "kpi" }, [el("div", { class: "label" }, "기간 내 낙찰 건수"), el("div", { class: "value" }, String(s.count))]),
    el("div", { class: "kpi" }, [el("div", { class: "label" }, "평균 낙찰률"), el("div", { class: "value" }, s.avgRate == null ? "-" : `${s.avgRate}%`)]),
    el("div", { class: "kpi", html: `<div class="label">상위 낙찰자</div>${top ? `<ol>${top}</ol>` : '<div class="muted">-</div>'}` }),
  ]);
}

function table(rows, state) {
  if (!rows.length) return el("div", { class: "empty" }, "결과가 확인된 공고가 없습니다.");
  const t = el("table", { class: "list" });
  t.innerHTML = `<thead><tr><th>개찰일</th><th>공고명</th><th>기관</th><th>지역</th><th class="num">기초금액</th><th>낙찰자</th><th class="num">낙찰금액</th><th class="num">낙찰률</th><th class="num">참가</th><th>상태</th></tr></thead>`;
  const tbody = el("tbody");
  for (const r of rows) {
    const tr = el("tr", { class: r.notice.interest ? "interest" : "", onclick: () => state.select(r.notice) });
    tr.innerHTML = `
      <td data-label="개찰일" class="nowrap">${esc(formatDate(r.award?.opened_at ?? r.notice.open_at))}</td>
      <td class="title-cell"><span class="chips">${serviceChip(r.notice)}${trackChip(r.notice.track)}${interestChip(r.notice)}</span><span class="title-text">${esc(r.title)}</span></td>
      <td data-label="기관">${esc(r.agency || "-")}</td>
      <td data-label="지역" class="nowrap">${esc(r.region)}</td>
      <td data-label="기초금액" class="num">${esc(formatAmount(r.budget))}</td>
      <td data-label="낙찰자">${esc(r.winner || "-")}</td>
      <td data-label="낙찰금액" class="num">${esc(formatAmount(r.amount))}</td>
      <td data-label="낙찰률" class="num">${r.rate === "" ? "-" : `${esc(r.rate)}%`}</td>
      <td data-label="참가" class="num">${r.participants === "" ? "-" : esc(r.participants)}</td>
      <td data-label="상태">${statusChip(r.notice.status)}</td>`;
    tbody.append(tr);
  }
  t.append(tbody);
  return t;
}

export function render(container, state) {
  const scoped = applyFilters(state.notices, { ...state.filters, statuses: RESULT_STATUSES });
  const rows = joinRows(scoped, state.awardByKey)
    .sort((a, b) => (a.opened < b.opened ? 1 : a.opened > b.opened ? -1 : 0));
  const shown = applyLocal(rows);
  const rerender = () => render(container, state);
  container.replaceChildren(
    filtersBar(rows, rerender),
    summaryCards(shown),
    el("div", { class: "section" }, [
      el("h2", {}, ["낙찰·결과 이력", el("span", { class: "count" }, `${shown.length}건`)]),
      table(shown, state),
    ]),
  );
}
