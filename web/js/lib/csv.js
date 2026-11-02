// CSV 직렬화 (순수 함수). Excel 한글 호환을 위해 UTF-8 BOM + CRLF.
const BOM = "﻿";

function cell(value) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function toCsv(rows, columns) {
  const header = columns.map((c) => cell(c.label)).join(",");
  const body = rows.map((row) => columns.map((c) => cell(row[c.key])).join(","));
  return BOM + [header, ...body].join("\r\n");
}
