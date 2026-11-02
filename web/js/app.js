// 탭 라우팅 + 공통 필터 상태 + 수집 상태 배지.
import { loadAll } from "./data.js";
import { formatDateTime } from "./lib/format.js";
import { statusBadgeClass } from "./lib/stats.js";
import * as dashboard from "./views/dashboard.js";
import * as calendar from "./views/calendar.js";
import { closeDetail, openDetail } from "./views/detail.js";

const VIEWS = { dashboard, calendar };
const BADGE_TEXT = { ok: "수집 정상", stale: "갱신 지연", fail: "수집 실패" };

let state = {
  notices: [], awards: [], awardByKey: new Map(), meta: null, now: new Date(),
  filters: { track: "all", interestOnly: false, query: "" },
  select: null,
};

function currentTab() {
  const tab = location.hash.replace("#", "") || "dashboard";
  return VIEWS[tab] ? tab : "dashboard";
}

function renderBadge() {
  const badge = document.getElementById("status-badge");
  const cls = statusBadgeClass(state.meta, state.now);
  badge.className = `badge badge-${cls}`;
  badge.textContent = BADGE_TEXT[cls];
  document.getElementById("run-at").textContent = state.meta?.run_at
    ? `마지막 갱신 ${formatDateTime(state.meta.run_at)}` : "";
  const banner = document.getElementById("error-banner");
  const errors = state.meta?.errors ?? [];
  banner.hidden = errors.length === 0;
  banner.textContent = errors.length ? `수집 오류: ${errors.join(" / ")}` : "";
}

function render() {
  const tab = currentTab();
  document.querySelectorAll(".tabs a").forEach((a) => a.classList.toggle("active", a.dataset.tab === tab));
  VIEWS[tab].render(document.getElementById("view"), state);
}

function setFilters(patch) {
  state = { ...state, filters: { ...state.filters, ...patch } };
  render();
}

function bindControls() {
  document.querySelectorAll(".seg [data-track]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg [data-track]").forEach((b) => b.classList.toggle("active", b === btn));
      setFilters({ track: btn.dataset.track });
    });
  });
  document.getElementById("interest-only").addEventListener("change", (e) => setFilters({ interestOnly: e.target.checked }));
  document.getElementById("query").addEventListener("input", (e) => setFilters({ query: e.target.value }));
  document.getElementById("modal-close").addEventListener("click", closeDetail);
  document.getElementById("modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeDetail(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDetail(); });
  window.addEventListener("hashchange", render);
}

export function registerView(name, mod) {
  VIEWS[name] = mod;
}

async function boot() {
  const data = await loadAll();
  const awardByKey = new Map(data.awards.map((a) => [a.key, a]));
  state = {
    ...state, ...data, awardByKey,
    select: (notice) => openDetail(notice, awardByKey.get(notice.key)),
  };
  bindControls();
  renderBadge();
  render();
}

boot();
