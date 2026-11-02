import test from "node:test";
import assert from "node:assert/strict";
import { buildMonthGrid, shiftMonth, toEvents } from "./calendar.js";

const notices = [
  { key: "a", track: "public", interest: true, title: "A", close_at: "2026-11-16T14:00", open_at: "2026-11-17T15:00" },
  { key: "b", track: "apt", interest: false, title: "B", close_at: "2026-11-16T17:00", open_at: null },
  { key: "c", track: "public", interest: false, title: "C", close_at: null, open_at: null },
];

test("toEvents makes close and open events and skips missing dates", () => {
  const events = toEvents(notices);
  assert.deepEqual(events.map((e) => [e.date, e.type, e.notice.key]), [
    ["2026-11-16", "close", "a"], ["2026-11-17", "open", "a"], ["2026-11-16", "close", "b"],
  ]);
});

test("buildMonthGrid 2026-11 has 42 cells starting Sunday", () => {
  const grid = buildMonthGrid(2026, 11, []);
  assert.equal(grid.label, "2026년 11월");
  assert.equal(grid.weeks.length, 6);
  assert.equal(grid.weeks.flat().length, 42);
  assert.equal(grid.weeks[0][0].date, "2026-11-01");
  assert.equal(grid.weeks[0][0].inMonth, true);
  assert.equal(grid.weeks[4][1].date, "2026-11-30");
  assert.equal(grid.weeks[4][2].date, "2026-12-01");
  assert.equal(grid.weeks[4][2].inMonth, false);
});

test("buildMonthGrid 2026-10 leading days belong to previous month", () => {
  const grid = buildMonthGrid(2026, 10, []);
  assert.equal(grid.weeks[0][0].date, "2026-09-27");
  assert.equal(grid.weeks[0][0].inMonth, false);
  assert.equal(grid.weeks[0][4].date, "2026-10-01");
});

test("buildMonthGrid places events on correct cell", () => {
  const grid = buildMonthGrid(2026, 11, toEvents(notices));
  const cell16 = grid.weeks.flat().find((c) => c.date === "2026-11-16");
  const cell17 = grid.weeks.flat().find((c) => c.date === "2026-11-17");
  assert.equal(cell16.events.length, 2);
  assert.equal(cell17.events.length, 1);
  assert.equal(cell17.events[0].type, "open");
});

test("build_month_grid_skips_events_without_date", () => {
  const grid = buildMonthGrid(2026, 11, toEvents([notices[2]]));
  assert.equal(grid.weeks.flat().reduce((s, c) => s + c.events.length, 0), 0);
});

test("shiftMonth wraps year", () => {
  assert.deepEqual(shiftMonth(2026, 12, 1), { year: 2027, month: 1 });
  assert.deepEqual(shiftMonth(2026, 1, -1), { year: 2025, month: 12 });
  assert.deepEqual(shiftMonth(2026, 6, 0), { year: 2026, month: 6 });
});
