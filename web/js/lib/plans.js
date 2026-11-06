// 발주계획 화면용 순수 함수: 상태 판정·필터·정렬·요약. 입력을 바꾸지 않는다.
import { categoryOf } from "./filter.js";
import { dday } from "./format.js";

export const PLAN_STATUS_LABELS = Object.freeze({ planned: "공고 전", overdue: "예정월 경과", noticed: "공고됨" });
export const RECENT_DAYS = 7;
const NO_MONTH = "none";

const compact = (s) => String(s ?? "").replace(/\s+/g, "");
const monthKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

// noticed: 이 계획으로 입찰공고가 나감 / overdue: 예정월이 지났는데 공고 없음 / planned: 그 외
export function planStatus(plan, now = new Date()) {
  if (plan.notice_nos?.length) return "noticed";
  return plan.order_ym && plan.order_ym < monthKey(now) ? "overdue" : "planned";
}

// 상태별로 나눈다(각 묶음 안의 순서는 입력 순서 그대로).
export function groupByStatus(plans, now = new Date()) {
  const of = (status) => plans.filter((p) => planStatus(p, now) === status);
  return { planned: of("planned"), overdue: of("overdue"), noticed: of("noticed") };
}

export function isRecentPlan(plan, now = new Date()) {
  return [plan.posted_at, plan.changed_at].some((iso) => {
    const n = dday(iso, now);
    return n !== null && n <= 0 && n > -RECENT_DAYS; // 오늘 포함 RECENT_DAYS일
  });
}

function matchesQuery(plan, query) {
  const q = compact(query);
  if (!q) return true;
  return [plan.title, plan.agency, plan.parent_agency, plan.dept].map(compact).join("\u0000").includes(q);
}

function matchesStatus(plan, status, now) {
  if (status === "all") return true;
  const actual = planStatus(plan, now);
  return status === "pending" ? actual !== "noticed" : actual === status;
}

// global = 화면 공통 필터, local = 발주계획 탭 전용 필터. 발주계획은 공공기관(나라장터)만 있다.
export function filterPlans(plans, global = {}, local = {}, now = new Date()) {
  const { track = "all", category = "all", interestOnly = false, query = "" } = global;
  const { status = "pending", month = "all", region = "all", method = "all" } = local;
  if (track === "apt") return [];
  return plans.filter((p) =>
    (category === "all" || categoryOf(p) === category)
    && (!interestOnly || p.interest)
    && matchesQuery(p, query)
    && matchesStatus(p, status, now)
    && (month === "all" || (p.order_ym ?? NO_MONTH) === month)
    && (region === "all" || (p.region || "미분류") === region)
    && (method === "all" || p.contract_method === method));
}

const LOCAL_VALUES = Object.freeze({
  month: (p) => p.order_ym ?? NO_MONTH,
  region: (p) => p.region || "미분류",
  method: (p) => p.contract_method,
});

// 공통 필터가 바뀌어 선택지에서 사라진 탭 전용 필터 값은 "전체"로 되돌린다(보이지 않는 조건으로 빈 목록이 되지 않도록).
export function resetStaleFilters(local, plans) {
  const stale = Object.entries(LOCAL_VALUES)
    .filter(([key, valueOf]) => local[key] !== "all" && !plans.some((p) => valueOf(p) === local[key]))
    .map(([key]) => [key, "all"]);
  return { ...local, ...Object.fromEntries(stale) };
}

// 다가오는 달(이번 달 포함, 가까운 달부터) → 예정월 미정 → 지난 달(최근 달부터). 같은 달은 금액 큰 순.
export function sortPlans(plans, now = new Date()) {
  const current = monthKey(now);
  const group = (p) => (!p.order_ym ? 1 : p.order_ym >= current ? 0 : 2);
  return [...plans].sort((a, b) => {
    if (group(a) !== group(b)) return group(a) - group(b);
    if (a.order_ym !== b.order_ym) return (a.order_ym < b.order_ym ? -1 : 1) * (group(a) === 2 ? -1 : 1);
    return (b.amount ?? 0) - (a.amount ?? 0);
  });
}

export function planSummary(plans, now = new Date()) {
  return {
    count: plans.length,
    target: plans.filter((p) => categoryOf(p) === "target").length,
    interest: plans.filter((p) => p.interest).length,
    recent: plans.filter((p) => isRecentPlan(p, now)).length,
    amount: plans.reduce((sum, p) => sum + (p.amount ?? 0), 0),
  };
}

export function orderMonthLabel(orderYm) {
  if (!orderYm) return "미정";
  const [year, month] = orderYm.split("-");
  return `${year}년 ${Number(month)}월`;
}

// 계획에 연결된 공고번호마다, 대시보드가 수집한 공고가 있으면 함께 돌려준다.
export function linkedNotices(plan, noticeByNo) {
  return (plan.notice_nos ?? []).map((no) => ({ no, notice: noticeByNo.get(no) ?? null }));
}
