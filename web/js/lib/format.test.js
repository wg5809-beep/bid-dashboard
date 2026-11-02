import test from "node:test";
import assert from "node:assert/strict";
import {
  ddayLabel, dday, formatAmount, formatDate, formatDateTime,
  regionLabel, statusLabel, trackLabel,
} from "./format.js";

const NOW = new Date(2026, 10, 2, 9, 0); // 2026-11-02 (월)

test("formatAmount units", () => {
  assert.equal(formatAmount(null), "-");
  assert.equal(formatAmount(0), "-");
  assert.equal(formatAmount(12000000), "1,200만원");
  assert.equal(formatAmount(350000000), "3.5억원");
  assert.equal(formatAmount(100000000), "1억원");
  assert.equal(formatAmount(5000), "0.5만원");
});

test("formatDate and formatDateTime", () => {
  assert.equal(formatDate("2026-11-16T14:00"), "11/16(월)");
  assert.equal(formatDateTime("2026-11-16T14:00"), "11/16 14:00");
  assert.equal(formatDate(null), "-");
  assert.equal(formatDateTime(""), "-");
});

test("dday and ddayLabel", () => {
  assert.equal(dday("2026-11-05T14:00", NOW), 3);
  assert.equal(dday("2026-11-02T23:00", NOW), 0);
  assert.equal(dday("2026-10-30T10:00", NOW), -3);
  assert.equal(dday(null, NOW), null);
  assert.equal(ddayLabel("2026-11-05T14:00", NOW), "D-3");
  assert.equal(ddayLabel("2026-11-02T23:00", NOW), "오늘");
  assert.equal(ddayLabel("2026-10-30T10:00", NOW), "마감");
  assert.equal(ddayLabel(undefined, NOW), "-");
});

test("statusLabel all statuses", () => {
  const expected = {
    open: "공고중", closed: "마감", opened: "개찰완료", awarded: "낙찰", failed: "유찰",
    rebid: "재입찰", cancelled: "취소", unknown: "결과미확인",
  };
  for (const [k, v] of Object.entries(expected)) assert.equal(statusLabel(k), v);
  assert.equal(statusLabel("weird"), "weird");
});

test("trackLabel and regionLabel", () => {
  assert.equal(trackLabel("public"), "공공기관");
  assert.equal(trackLabel("apt"), "아파트");
  assert.equal(regionLabel("전남광주"), "전남광주");
  assert.equal(regionLabel(null), "미분류");
});
