// 지역 지도 뷰: 시도 SVG choropleth + 지역 클릭 목록 + 지역별 건수 표.
import { el, esc } from "../lib/dom.js";
import { ACTIVE_STATUSES, applyFilters, sortByClose } from "../lib/filter.js";
import { noticeTable } from "../lib/rows.js";
import { countByRegion } from "../lib/stats.js";

const HOME_REGIONS = ["전남광주"];
const SHADES = ["#e9edf2", "#c9dbf5", "#9dbdee", "#5f91dc", "#2f66c2"];
let svgText = null;
let selected = null;

function shade(count, max) {
  if (!count) return SHADES[0];
  const step = Math.ceil((count / Math.max(max, 1)) * (SHADES.length - 1));
  return SHADES[Math.max(1, Math.min(SHADES.length - 1, step))];
}

async function loadSvg() {
  if (svgText) return svgText;
  const res = await fetch("assets/korea-sido.svg");
  svgText = res.ok ? await res.text() : "";
  return svgText;
}

function paint(wrap, counts, onPick) {
  const max = Math.max(0, ...Object.values(counts));
  wrap.querySelectorAll("[data-region]").forEach((node) => {
    const region = node.dataset.region;
    const n = counts[region] ?? 0;
    node.setAttribute("fill", shade(n, max));
    node.classList.toggle("home", HOME_REGIONS.includes(region));
    node.classList.toggle("selected", region === selected);
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", "button");
    node.setAttribute("aria-label", `${region} ${n}건`);
    node.onclick = () => onPick(region);
    node.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(region); } };
  });
}

function regionTable(counts, onPick) {
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const table = el("table", { class: "list region-table" });
  table.innerHTML = `<thead><tr><th>지역</th><th class="num">진행중 공고</th></tr></thead>`;
  const tbody = el("tbody");
  for (const [region, n] of rows) {
    const tr = el("tr", { class: HOME_REGIONS.includes(region) ? "interest" : "", onclick: () => onPick(region) });
    tr.innerHTML = `<td data-label="지역">${esc(region)}</td><td data-label="진행중" class="num">${n}</td>`;
    tbody.append(tr);
  }
  table.append(tbody);
  return rows.length ? table : el("div", { class: "empty" }, "진행중 공고가 없습니다.");
}

function legend(max) {
  const stops = SHADES.map((c, i) => `<span><span class="sw" style="background:${c}"></span>${i === 0 ? "0건" : i === SHADES.length - 1 ? `${max}건` : ""}</span>`).join("");
  return el("div", { class: "legend", html: `${stops}<span><span class="sw" style="border:2px solid var(--interest)"></span>관심지역(전남광주)</span>` });
}

export async function render(container, state) {
  const scoped = applyFilters(state.notices, state.filters);
  const active = scoped.filter((n) => ACTIVE_STATUSES.includes(n.status));
  const counts = countByRegion(scoped);
  const max = Math.max(0, ...Object.values(counts));
  const pick = (region) => { selected = selected === region ? null : region; render(container, state); };

  const wrap = el("div", { class: "map-wrap panel" });
  wrap.innerHTML = (await loadSvg()) || '<div class="empty">지도 파일을 불러오지 못했습니다.</div>';
  paint(wrap, counts, pick);

  const listed = sortByClose(selected ? active.filter((n) => (n.region || "미분류") === selected) : active);
  const side = el("div", {}, [
    el("div", { class: "section" }, [
      el("h2", {}, [selected ? `${selected} 진행중 공고` : "전체 진행중 공고 (지역을 누르면 좁혀집니다)", el("span", { class: "count" }, `${listed.length}건`)]),
      noticeTable(listed, { now: state.now, onSelect: state.select, emptyText: "해당 지역에 진행중 공고가 없습니다." }),
    ]),
  ]);
  container.replaceChildren(
    el("div", { class: "map-layout" }, [el("div", {}, [wrap, legend(max), regionTable(counts, pick)]), side]),
  );
}
