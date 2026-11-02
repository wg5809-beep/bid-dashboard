import test from "node:test";
import assert from "node:assert/strict";
import { toCsv } from "./csv.js";

const columns = [{ key: "title", label: "공고명" }, { key: "amount", label: "금액" }];

test("toCsv escapes comma quote newline and has BOM CRLF", () => {
  const rows = [{ title: 'a,b "c"\nd', amount: 1200 }, { title: "plain", amount: null }];
  const csv = toCsv(rows, columns);
  assert.ok(csv.startsWith("\uFEFF"));
  const lines = csv.slice(1).split("\r\n");
  assert.equal(lines[0], "공고명,금액");
  assert.equal(lines[1], '"a,b ""c""\nd",1200');
  assert.equal(lines[2], "plain,");
  assert.equal(lines.length, 3);
});

test("toCsv uses labels as header in column order", () => {
  const csv = toCsv([], [{ key: "b", label: "B" }, { key: "a", label: "A" }]);
  assert.equal(csv, "\uFEFFB,A");
});
