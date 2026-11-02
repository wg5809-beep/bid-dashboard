import test from "node:test";
import assert from "node:assert/strict";
import { applyFilters, sortByClose } from "./filter.js";

const notices = [
  { key: "public:A", track: "public", title: "외부회계감사 용역", agency: "나주시", demand_agency: "나주시", interest: true, status: "open", close_at: "2026-11-16T14:00" },
  { key: "public:B", track: "public", title: "타당성 조사", agency: "서울시", demand_agency: null, interest: false, status: "closed", close_at: "2026-11-10T14:00" },
  { key: "apt:C", track: "apt", title: "[전북] 회계감사", agency: "전주 아파트", complex_name: "전주 아파트", interest: false, status: "open", close_at: null },
];

test("applyFilters track and interest", () => {
  assert.deepEqual(applyFilters(notices, { track: "all", interestOnly: false, query: "" }).map((n) => n.key), ["public:A", "public:B", "apt:C"]);
  assert.deepEqual(applyFilters(notices, { track: "apt", interestOnly: false, query: "" }).map((n) => n.key), ["apt:C"]);
  assert.deepEqual(applyFilters(notices, { track: "all", interestOnly: true, query: "" }).map((n) => n.key), ["public:A"]);
});

test("applyFilters query ignores spaces and searches agency and complex", () => {
  assert.deepEqual(applyFilters(notices, { track: "all", interestOnly: false, query: "회계 감사" }).map((n) => n.key), ["public:A", "apt:C"]);
  assert.deepEqual(applyFilters(notices, { track: "all", interestOnly: false, query: "전주" }).map((n) => n.key), ["apt:C"]);
});

test("applyFilters by statuses", () => {
  assert.deepEqual(applyFilters(notices, { track: "all", interestOnly: false, query: "", statuses: ["closed"] }).map((n) => n.key), ["public:B"]);
});

test("applyFilters returns new array and does not mutate", () => {
  const copy = JSON.parse(JSON.stringify(notices));
  const out = applyFilters(notices, { track: "all", interestOnly: false, query: "" });
  assert.notEqual(out, notices);
  assert.deepEqual(notices, copy);
});

test("sortByClose puts null last and does not mutate", () => {
  const sorted = sortByClose(notices);
  assert.deepEqual(sorted.map((n) => n.key), ["public:B", "public:A", "apt:C"]);
  assert.equal(notices[0].key, "public:A");
});

test("RESULT_STATUSES includes opened so awaiting-result notices are listed", async () => {
  const { RESULT_STATUSES } = await import("./filter.js");
  assert.ok(RESULT_STATUSES.includes("opened"));
});
