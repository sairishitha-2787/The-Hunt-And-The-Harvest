import { test } from "node:test";
import assert from "node:assert/strict";

import { compare, describePosition, toPosition, womanDoesIt } from "./logic.js";
import { ANSWERS, QUESTIONS } from "./questions.js";

test("toPosition: partner A's answers run 0 to 4", () => {
  assert.equal(toPosition("always_me", "A"), 0);
  assert.equal(toPosition("usually_me", "A"), 1);
  assert.equal(toPosition("equal", "A"), 2);
  assert.equal(toPosition("usually_partner", "A"), 3);
  assert.equal(toPosition("always_partner", "A"), 4);
});

test("toPosition: partner B's answers are mirrored", () => {
  assert.equal(toPosition("always_me", "B"), 4);
  assert.equal(toPosition("usually_me", "B"), 3);
  assert.equal(toPosition("equal", "B"), 2);
  assert.equal(toPosition("usually_partner", "B"), 1);
  assert.equal(toPosition("always_partner", "B"), 0);
});

test("toPosition: third person is null for both partners", () => {
  assert.equal(toPosition("third_person", "A"), null);
  assert.equal(toPosition("third_person", "B"), null);
});

test("toPosition: both say 'me' -> opposite ends", () => {
  assert.equal(compare(toPosition("always_me", "A"), toPosition("always_me", "B")), "disagree");
});

test("toPosition: consistent answers land on the same position", () => {
  assert.equal(toPosition("usually_me", "A"), toPosition("usually_partner", "B"));
});

test("toPosition: rejects unknown answers and partners", () => {
  assert.throws(() => toPosition("sometimes", "A"));
  assert.throws(() => toPosition("always_me", "C"));
  assert.throws(() => toPosition(undefined, "A"));
});

test("every answer option maps for both partners", () => {
  for (const { value } of ANSWERS) {
    for (const who of ["A", "B"]) {
      const p = toPosition(value, who);
      assert.ok(p === null || (Number.isInteger(p) && p >= 0 && p <= 4));
    }
  }
});

test("compare: difference 0 / 1 / 2+", () => {
  assert.equal(compare(2, 2), "agree");
  assert.equal(compare(0, 0), "agree");
  assert.equal(compare(1, 2), "slightly different");
  assert.equal(compare(4, 3), "slightly different");
  assert.equal(compare(1, 3), "disagree");
  assert.equal(compare(0, 4), "disagree");
});

test("compare: third person", () => {
  assert.equal(compare(null, null), "agree");
  assert.equal(compare(null, 2), "disagree");
  assert.equal(compare(0, null), "disagree");
});

test("describePosition uses the partners' names", () => {
  assert.equal(describePosition(0, "Ana", "Ben"), "Always Ana");
  assert.equal(describePosition(1, "Ana", "Ben"), "Usually Ana");
  assert.equal(describePosition(2, "Ana", "Ben"), "About equal");
  assert.equal(describePosition(3, "Ana", "Ben"), "Usually Ben");
  assert.equal(describePosition(4, "Ana", "Ben"), "Always Ben");
  assert.equal(describePosition(null, "Ana", "Ben"), "A third person");
});

test("womanDoesIt matches 'always or usually the woman'", () => {
  assert.equal(womanDoesIt(0, "A"), true);
  assert.equal(womanDoesIt(1, "A"), true);
  assert.equal(womanDoesIt(2, "A"), false);
  assert.equal(womanDoesIt(3, "A"), false);
  assert.equal(womanDoesIt(3, "B"), true);
  assert.equal(womanDoesIt(1, "B"), false);
  assert.equal(womanDoesIt(null, "A"), null);
  assert.equal(womanDoesIt(0, null), null);
});

test("questions: 6 ISSP items first, then 4 invisible-work items", () => {
  assert.equal(QUESTIONS.length, 10);
  assert.deepEqual(
    QUESTIONS.filter((q) => q.issp).map((q) => q.id),
    ["laundry", "plan_activities", "care_sick", "groceries", "cleaning", "meals"],
  );
  assert.equal(QUESTIONS.filter((q) => !q.issp).length, 4);
  assert.equal(new Set(QUESTIONS.map((q) => q.id)).size, 10);
});
