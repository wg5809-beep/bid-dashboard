// 공고 목록 표(데스크톱) / 카드(모바일) 공용 렌더러.
import { el, esc } from "./dom.js";
import { ddayLabel, dday, formatAmount, formatDate, formatDateTime, regionLabel, statusLabel, trackLabel } from "./format.js";

export function interestChip(notice) {
  if (!notice.interest) return "";
  const extra = notice.interest_reason === "지역제한" && notice.limit_regions?.length
    ? ` · ${esc(notice.limit_regions[0])}` : "";
  return `<span class="chip chip-interest">${esc(notice.interest_reason ?? "관심지역")}${extra}</span>`;
}

export function trackChip(track) {
  return `<span class="chip chip-${esc(track)}">${esc(trackLabel(track))}</span>`;
}

export function statusChip(status) {
  return `<span class="chip chip-status ${esc(status)}">${esc(statusLabel(status))}</span>`;
}

function ddayCell(notice, now) {
  const n = dday(notice.close_at, now);
  const urgent = n !== null && n >= 0 && n <= 3 && ["open"].includes(notice.status);
  return `<span class="dday ${urgent ? "urgent" : ""}">${esc(ddayLabel(notice.close_at, now))}</span> <span class="muted">${esc(formatDateTime(notice.close_at))}</span>`;
}

export function noticeTable(notices, { now, onSelect, emptyText = "표시할 공고가 없습니다." }) {
  if (!notices.length) return el("div", { class: "empty" }, emptyText);
  const table = el("table", { class: "list" });
  table.innerHTML = `<thead><tr>
    <th>공고명</th><th>기관</th><th>지역</th><th class="num">기초금액</th><th>마감</th><th>개찰</th><th>상태</th>
  </tr></thead>`;
  const tbody = el("tbody");
  for (const n of notices) {
    const tr = el("tr", { class: n.interest ? "interest" : "", onclick: () => onSelect(n) });
    tr.innerHTML = `
      <td class="title-cell">${trackChip(n.track)}${interestChip(n)}${esc(n.title)}</td>
      <td data-label="기관">${esc(n.agency ?? "-")}${n.demand_agency && n.demand_agency !== n.agency ? ` <span class="muted">(${esc(n.demand_agency)})</span>` : ""}</td>
      <td data-label="지역" class="nowrap">${esc(regionLabel(n.region))}</td>
      <td data-label="기초금액" class="num">${esc(formatAmount(n.budget ?? n.estimate))}</td>
      <td data-label="마감" class="nowrap">${ddayCell(n, now)}</td>
      <td data-label="개찰" class="nowrap">${esc(formatDate(n.open_at))}</td>
      <td data-label="상태">${statusChip(n.status)}</td>`;
    tbody.append(tr);
  }
  table.append(tbody);
  return table;
}
