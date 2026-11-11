import test from "node:test";
import assert from "node:assert/strict";
import { awardSummary, countByRegion, kpis, statusBadgeClass } from "./stats.js";

const NOW = new Date(2026, 10, 2, 9, 0); // 2026-11-02 월요일
const notices = [
  { key: "1", status: "open", interest: true, region: "전남광주", first_seen: "2026-11-02", close_at: "2026-11-05T14:00", open_at: "2026-11-06T10:00" },
  { key: "2", status: "open", interest: false, region: "서울", first_seen: "2026-11-02", close_at: "2026-11-08T14:00", open_at: "2026-11-12T10:00" },
  { key: "3", status: "closed", interest: false, region: "전북", first_seen: "2026-10-20", close_at: "2026-11-01T14:00", open_at: "2026-11-03T10:00" },
  { key: "4", status: "open", interest: false, region: "서울", first_seen: "2026-10-28", close_at: "2026-11-20T14:00", open_at: null },
  { key: "5", status: "awarded", interest: true, region: "전남광주", first_seen: "2026-09-01", close_at: "2026-09-20T14:00", open_at: "2026-09-21T10:00" },
];

test("kpis counts", () => {
  const k = kpis(notices, [], NOW);
  assert.equal(k.newToday, 2);
  assert.equal(k.closingIn7, 2); // 11/05, 11/08 (11/01은 과거, 11/20은 7일 밖)
  assert.equal(k.interestOpen, 1); // key 1 (5는 낙찰)
  assert.equal(k.openingThisWeek, 2); // 11/06, 11/03
});

test("countByRegion only active", () => {
  assert.deepEqual(countByRegion(notices), { "전남광주": 1, "서울": 2, "전북": 1 });
});

test("awardSummary top winners and avg rate", () => {
  const awards = [
    { winner: "A회계법인", rate: 88 }, { winner: "B회계법인", rate: 90 },
    { winner: "A회계법인", rate: null }, { winner: null, rate: 85 },
  ];
  const s = awardSummary(awards);
  assert.equal(s.count, 4);
  assert.equal(s.avgRate, 87.7);
  assert.deepEqual(s.topWinners, [{ name: "A회계법인", count: 2 }, { name: "B회계법인", count: 1 }]);
  assert.deepEqual(awardSummary([]), { count: 0, avgRate: null, topWinners: [] });
});

test("statusBadgeClass for failed meta", () => {
  assert.equal(statusBadgeClass({ ok: false, run_at: "2026-11-02T07:00" }, NOW), "fail");
  assert.equal(statusBadgeClass({ ok: true, run_at: "2026-11-02T07:00" }, NOW), "ok");
  assert.equal(statusBadgeClass({ ok: true, run_at: "2026-10-30T07:00" }, NOW), "stale");
  assert.equal(statusBadgeClass(null, NOW), "fail");
});

test("statusBadgeClass allows the Sunday gap after a Saturday run", () => {
  const saturdayRun = { ok: true, run_at: "2026-10-31T08:23" }; // 일요일은 수집하지 않는다
  assert.equal(statusBadgeClass(saturdayRun, new Date(2026, 10, 1, 22, 0)), "ok");   // 일요일 밤
  assert.equal(statusBadgeClass(saturdayRun, new Date(2026, 10, 2, 9, 0)), "ok");    // 월요일 아침
  assert.equal(statusBadgeClass(saturdayRun, new Date(2026, 10, 2, 21, 0)), "stale"); // 월요일 수집도 빠짐
});

test("kpis newToday uses local date even before 09:00", () => {
  const early = new Date(2026, 10, 2, 1, 0); // 01:00 로컬 → UTC는 전날일 수 있음
  assert.equal(kpis(notices, [], early).newToday, 2);
});

test("kpis counts active target-service notices", () => {
  const rows = [
    { key: "a", status: "open", interest: false, category: "target", first_seen: "2026-10-01", close_at: null, open_at: null },
    { key: "b", status: "closed", interest: false, category: "target", first_seen: "2026-10-01", close_at: null, open_at: null },
    { key: "c", status: "awarded", interest: false, category: "target", first_seen: "2026-10-01", close_at: null, open_at: null },
    { key: "d", status: "open", interest: false, category: "other", first_seen: "2026-10-01", close_at: null, open_at: null },
  ];
  assert.equal(kpis(rows, [], NOW).targetOpen, 2);
});
