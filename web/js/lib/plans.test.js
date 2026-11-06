import test from "node:test";
import assert from "node:assert/strict";
import { filterPlans, groupByStatus, isRecentPlan, linkedNotices, orderMonthLabel, planStatus, planSummary, resetStaleFilters, sortPlans } from "./plans.js";

const NOW = new Date(2026, 10, 6, 9, 0); // 2026-11-06
const plans = [
  { key: "plan:A", title: "2027회계연도 외부회계감사 용역", agency: "나주시", parent_agency: "전남광주통합특별시", dept: "회계과", order_ym: "2026-12", amount: 30_000_000, contract_method: "제한경쟁", notice_nos: [], region: "전남광주", interest: true, category: "target", service: "회계감사", posted_at: "2026-11-05T10:00", changed_at: null },
  { key: "plan:B", title: "타당성 조사 용역", agency: "서울시", parent_agency: "서울특별시", dept: "기획과", order_ym: "2026-09", amount: 100_000_000, contract_method: "일반경쟁", notice_nos: [], region: "서울", interest: false, category: "other", service: null, posted_at: "2026-01-10T10:00", changed_at: null },
  { key: "plan:C", title: "재무결산 위탁용역", agency: "법무부", parent_agency: "법무부", dept: "운영지원과", order_ym: "2026-10", amount: 50_000_000, contract_method: "제한경쟁", notice_nos: ["R26BK01805078", "R26BK00000009"], region: "미분류", interest: false, category: "target", service: "PA", posted_at: "2026-10-29T21:08", changed_at: "2026-11-02T09:00" },
  { key: "plan:D", title: "세무 자문", agency: "부산항만공사", parent_agency: "부산항만공사", dept: "재무팀", order_ym: null, amount: null, contract_method: "수의계약", notice_nos: [], region: "부산", interest: false, category: "target", service: "세무컨설팅", posted_at: null, changed_at: null },
];
const GLOBAL = { track: "all", category: "all", interestOnly: false, query: "" };
const LOCAL = { status: "pending", month: "all", region: "all", method: "all" };
const keys = (rows) => rows.map((p) => p.key);

test("planStatus: noticed, overdue, planned", () => {
  assert.equal(planStatus(plans[0], NOW), "planned");
  assert.equal(planStatus(plans[1], NOW), "overdue"); // 예정월(9월)이 지났는데 공고 없음
  assert.equal(planStatus(plans[2], NOW), "noticed");
  assert.equal(planStatus(plans[3], NOW), "planned"); // 예정월 미정
  assert.equal(planStatus({ ...plans[0], order_ym: "2026-11" }, NOW), "planned"); // 이번 달은 경과 아님
});

test("filterPlans default shows plans without a notice yet", () => {
  assert.deepEqual(keys(filterPlans(plans, GLOBAL, LOCAL, NOW)), ["plan:A", "plan:B", "plan:D"]);
  assert.deepEqual(keys(filterPlans(plans, GLOBAL, { ...LOCAL, status: "noticed" }, NOW)), ["plan:C"]);
  assert.equal(filterPlans(plans, GLOBAL, { ...LOCAL, status: "all" }, NOW).length, 4);
});

test("filterPlans applies shared filters; apartment track has no plans", () => {
  assert.deepEqual(keys(filterPlans(plans, { ...GLOBAL, category: "target" }, LOCAL, NOW)), ["plan:A", "plan:D"]);
  assert.deepEqual(keys(filterPlans(plans, { ...GLOBAL, interestOnly: true }, LOCAL, NOW)), ["plan:A"]);
  assert.deepEqual(keys(filterPlans(plans, { ...GLOBAL, query: "회계 과" }, LOCAL, NOW)), ["plan:A"]); // 담당부서도 검색
  assert.deepEqual(keys(filterPlans(plans, { ...GLOBAL, query: "서울특별시" }, LOCAL, NOW)), ["plan:B"]); // 총괄기관도 검색
  assert.deepEqual(filterPlans(plans, { ...GLOBAL, track: "apt" }, LOCAL, NOW), []);
  assert.equal(filterPlans(plans, { ...GLOBAL, track: "public" }, LOCAL, NOW).length, 3);
});

test("filterPlans local month, region, contract method", () => {
  assert.deepEqual(keys(filterPlans(plans, GLOBAL, { ...LOCAL, month: "2026-12" }, NOW)), ["plan:A"]);
  assert.deepEqual(keys(filterPlans(plans, GLOBAL, { ...LOCAL, month: "none" }, NOW)), ["plan:D"]);
  assert.deepEqual(keys(filterPlans(plans, GLOBAL, { ...LOCAL, region: "부산" }, NOW)), ["plan:D"]);
  assert.deepEqual(keys(filterPlans(plans, GLOBAL, { ...LOCAL, method: "수의계약" }, NOW)), ["plan:D"]);
});

test("sortPlans: upcoming months first (soonest, larger amount first), then undated, then past months newest first", () => {
  const same = { ...plans[0], key: "plan:E", amount: 90_000_000 };
  const thisMonth = { ...plans[0], key: "plan:F", order_ym: "2026-11" };
  const input = [plans[3], plans[1], plans[0], plans[2], same, thisMonth];
  assert.deepEqual(keys(sortPlans(input, NOW)), ["plan:F", "plan:E", "plan:A", "plan:D", "plan:C", "plan:B"]);
  assert.equal(input[0].key, "plan:D"); // 입력은 바꾸지 않는다
});

test("groupByStatus splits plans into planned, overdue and noticed, keeping order", () => {
  const groups = groupByStatus(sortPlans(plans, NOW), NOW);
  assert.deepEqual(keys(groups.planned), ["plan:A", "plan:D"]);
  assert.deepEqual(keys(groups.overdue), ["plan:B"]); // 예정월(9월)이 지났고 공고 없음
  assert.deepEqual(keys(groups.noticed), ["plan:C"]);
  assert.deepEqual(groupByStatus([], NOW), { planned: [], overdue: [], noticed: [] });
});

test("filterPlans status can pick only upcoming or only overdue plans", () => {
  assert.deepEqual(keys(filterPlans(plans, GLOBAL, { ...LOCAL, status: "planned" }, NOW)), ["plan:A", "plan:D"]);
  assert.deepEqual(keys(filterPlans(plans, GLOBAL, { ...LOCAL, status: "overdue" }, NOW)), ["plan:B"]);
});

test("isRecentPlan: posted or changed within 7 days", () => {
  assert.equal(isRecentPlan(plans[0], NOW), true);
  assert.equal(isRecentPlan(plans[1], NOW), false);
  assert.equal(isRecentPlan(plans[2], NOW), true); // 게시는 오래됐지만 4일 전 변경
  assert.equal(isRecentPlan(plans[3], NOW), false);
  assert.equal(isRecentPlan({ posted_at: "2026-10-31T23:00" }, NOW), true); // 오늘 포함 7일째
  assert.equal(isRecentPlan({ posted_at: "2026-10-30T23:00" }, NOW), false);
});

test("resetStaleFilters clears a tab filter whose value is no longer among the listed plans", () => {
  const picked = { status: "pending", month: "2026-12", region: "부산", method: "수의계약" };
  assert.deepEqual(resetStaleFilters(picked, plans), picked); // 모두 선택지에 있음 → 그대로
  assert.deepEqual(resetStaleFilters(picked, [plans[0]]), { status: "pending", month: "2026-12", region: "all", method: "all" });
  assert.deepEqual(resetStaleFilters({ ...picked, month: "none" }, [plans[3]]), { ...picked, month: "none" });
  assert.equal(picked.region, "부산"); // 입력은 바꾸지 않는다
});

test("planSummary counts and totals", () => {
  assert.deepEqual(planSummary(plans, NOW), { count: 4, target: 3, interest: 1, recent: 2, amount: 180_000_000 });
  assert.deepEqual(planSummary([], NOW), { count: 0, target: 0, interest: 0, recent: 0, amount: 0 });
});

test("orderMonthLabel", () => {
  assert.equal(orderMonthLabel("2026-12"), "2026년 12월");
  assert.equal(orderMonthLabel("2027-01"), "2027년 1월");
  assert.equal(orderMonthLabel(null), "미정");
});

test("linkedNotices pairs each notice number with the collected notice if any", () => {
  const byNo = new Map([["R26BK01805078", { key: "public:R26BK01805078", title: "재무결산" }]]);
  assert.deepEqual(linkedNotices(plans[2], byNo), [
    { no: "R26BK01805078", notice: { key: "public:R26BK01805078", title: "재무결산" } },
    { no: "R26BK00000009", notice: null },
  ]);
  assert.deepEqual(linkedNotices(plans[0], byNo), []);
});
