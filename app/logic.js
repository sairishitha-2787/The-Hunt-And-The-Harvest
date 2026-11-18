// Pure functions: no DOM, no state. Tested in logic.test.js.
//
// Positions put both partners' answers on one shared scale:
//   0 = always A, 1 = usually A, 2 = about equal, 3 = usually B, 4 = always B.
// "Done by a third person" has no position (null).

const FROM_A = {
  always_me: 0,
  usually_me: 1,
  equal: 2,
  usually_partner: 3,
  always_partner: 4,
};

/** Map one partner's answer ("always_me", ...) to the shared 0-4 scale. */
export function toPosition(answer, who) {
  if (who !== "A" && who !== "B") throw new Error(`who must be "A" or "B", got ${who}`);
  if (answer === "third_person") return null;
  if (!(answer in FROM_A)) throw new Error(`Unknown answer: ${answer}`);
  return who === "A" ? FROM_A[answer] : 4 - FROM_A[answer];
}

/**
 * Compare two positions: "agree" (same), "slightly different" (1 apart),
 * "disagree" (2 or more apart).
 * Third person (null): both null -> "agree"; only one null -> "disagree",
 * since one partner says the couple doesn't do it at all.
 */
export function compare(a, b) {
  if (a === null && b === null) return "agree";
  if (a === null || b === null) return "disagree";
  const diff = Math.abs(a - b);
  if (diff === 0) return "agree";
  if (diff === 1) return "slightly different";
  return "disagree";
}

/** Describe a position with the partners' names, e.g. "Usually Sam". */
export function describePosition(position, nameA, nameB) {
  switch (position) {
    case null: return "A third person";
    case 0: return `Always ${nameA}`;
    case 1: return `Usually ${nameA}`;
    case 2: return "About equal";
    case 3: return `Usually ${nameB}`;
    case 4: return `Always ${nameB}`;
    default: throw new Error(`Unknown position: ${position}`);
  }
}

/**
 * Does this position count as "the woman always or usually does it",
 * the measure behind the country figures? womanIs is "A", "B" or null.
 * Returns null when it can't be said (no woman chosen, or third person),
 * matching ISSP, where third-person answers are left out.
 */
export function womanDoesIt(position, womanIs) {
  if (position === null || (womanIs !== "A" && womanIs !== "B")) return null;
  return womanIs === "A" ? position <= 1 : position >= 3;
}
