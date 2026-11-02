// 공고 상세 모달.
import { esc } from "../lib/dom.js";
import { categoryLabel, formatAmount, formatDateTime, regionLabel, serviceLabel, statusLabel, trackLabel } from "../lib/format.js";
import { interestChip } from "../lib/rows.js";

function row(label, value) {
  return `<dt>${esc(label)}</dt><dd>${value ?? "-"}</dd>`;
}

function awardBox(award) {
  if (!award) return "";
  return `<div class="award-box"><strong>낙찰 정보</strong>
    <dl class="detail">
      ${row("낙찰자", esc(award.winner ?? "-"))}
      ${row("사업자번호", esc(award.winner_bizno ?? "-"))}
      ${row("낙찰금액", esc(formatAmount(award.amount)))}
      ${row("예정가격", esc(formatAmount(award.planned_price)))}
      ${row("낙찰률", award.rate != null ? `${esc(award.rate)}%` : "-")}
      ${row("참가업체", award.participants != null ? `${esc(award.participants)}곳` : "-")}
      ${row("개찰일시", esc(formatDateTime(award.opened_at)))}
      ${row("낙찰일", esc(formatDateTime(award.awarded_at)))}
    </dl></div>`;
}

export function openDetail(notice, award) {
  const modal = document.getElementById("modal");
  const body = document.getElementById("modal-body");
  const history = (notice.history ?? []).map((h) =>
    `<li>차수 ${esc(h.notice_ord)} · 마감 ${esc(formatDateTime(h.close_at))} · ${esc(h.kind ?? "")}</li>`).join("");
  body.innerHTML = `
    <h3 id="modal-title">${interestChip(notice)}${esc(notice.title)}</h3>
    <dl class="detail">
      ${row("업무 구분", esc(categoryLabel(notice.category)) + (notice.category === "target" ? ` · ${esc(serviceLabel(notice.service))}` : ""))}
      ${row("트랙", esc(trackLabel(notice.track)) + (notice.source_system ? ` · ${esc(notice.source_system)}` : ""))}
      ${row("공고번호", `${esc(notice.notice_no)}${notice.notice_ord && notice.notice_ord !== "0" ? ` (차수 ${esc(notice.notice_ord)})` : ""}`)}
      ${row("공고기관", esc(notice.agency ?? "-"))}
      ${notice.demand_agency ? row("수요기관", esc(notice.demand_agency)) : ""}
      ${row("지역", esc(regionLabel(notice.region)) + (notice.limit_regions?.length ? ` <span class="muted">(제한: ${esc(notice.limit_regions.join(", "))})</span>` : ""))}
      ${row("공고일시", esc(formatDateTime(notice.posted_at)))}
      ${row("입찰마감", esc(formatDateTime(notice.close_at)))}
      ${row("개찰일시", esc(formatDateTime(notice.open_at)))}
      ${row("기초금액", esc(formatAmount(notice.budget)))}
      ${row("추정가격", esc(formatAmount(notice.estimate)))}
      ${row("계약방법", esc(notice.contract_method ?? "-"))}
      ${row("낙찰방법", esc(notice.award_method ?? "-"))}
      ${row("공고종류", esc(notice.kind ?? "-"))}
      ${row("상태", esc(statusLabel(notice.status)) + (notice.result_note ? ` · ${esc(notice.result_note)}` : ""))}
      ${row("원문", notice.url ? `<a href="${esc(notice.url)}" target="_blank" rel="noopener">원문 보기 ↗</a>` : "-")}
    </dl>
    ${history ? `<p class="muted">변경 이력</p><ul class="muted">${history}</ul>` : ""}
    ${awardBox(award)}`;
  modal.hidden = false;
}

export function closeDetail() {
  document.getElementById("modal").hidden = true;
}
