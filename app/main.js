// UI for the household tool. All state lives in the `state` variable below:
// nothing is stored in localStorage, cookies or the URL, and nothing is sent
// anywhere. Refreshing the page clears everything.

import { ANSWERS, QUESTIONS } from "./questions.js";
import { compare, describePosition, toPosition, womanDoesIt } from "./logic.js";

const app = document.getElementById("app");

let countryData = null; // loaded once at start, whatever the user picks later

let state = freshState();

function freshState() {
  return {
    screen: "intro", // intro -> answer-A -> pass -> answer-B -> reveal
    nameA: "",
    nameB: "",
    country: "", // code from country_tasks.json, or "" for none
    womanIs: "", // "A", "B" or "" (not said)
    answers: { A: {}, B: {} },
    error: "",
  };
}

// --- Small DOM helper ------------------------------------------------------
// Builds elements with textContent only, so names typed by users are never
// parsed as HTML.
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === false || value === null || value === undefined) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key in el && typeof value !== "string") el[key] = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

const nameOf = (who) => (who === "A" ? state.nameA : state.nameB);
const otherOf = (who) => (who === "A" ? "B" : "A");

// --- Rendering -------------------------------------------------------------
function render() {
  const screens = {
    intro: renderIntro,
    "answer-A": () => renderAnswers("A"),
    pass: renderPass,
    "answer-B": () => renderAnswers("B"),
    reveal: renderReveal,
  };
  app.replaceChildren(...screens[state.screen]());
  window.scrollTo(0, 0);
  // Move focus to the new heading so screen readers announce the new screen.
  const heading = app.querySelector("h1");
  if (heading) {
    heading.tabIndex = -1;
    heading.focus();
  }
}

function go(screen) {
  state.error = "";
  state.screen = screen;
  render();
}

function errorBox() {
  if (!state.error) return null;
  return h("p", { class: "error", role: "alert", id: "form-error" }, state.error);
}

function renderIntro() {
  const womanLabelA = h("span", {}, state.nameA || "Partner A");
  const womanLabelB = h("span", {}, state.nameB || "Partner B");

  const nameInput = (who) =>
    h("input", {
      id: `name-${who}`,
      name: `name-${who}`,
      type: "text",
      autocomplete: "off",
      maxlength: "40",
      value: nameOf(who),
      oninput: (e) => {
        const label = who === "A" ? womanLabelA : womanLabelB;
        label.textContent = e.target.value.trim() || `Partner ${who}`;
      },
    });

  const countrySelect = h(
    "select",
    { id: "country", name: "country", disabled: !countryData },
    h("option", { value: "" }, countryData ? "No country" : "Country figures unavailable"),
    countryData
      ? Object.entries(countryData.countries).map(([code, c]) =>
          h("option", { value: code, selected: code === state.country }, c.name))
      : [],
  );

  const womanOption = (value, label) =>
    h("label", { class: "choice" },
      h("input", { type: "radio", name: "woman", value, checked: state.womanIs === value }),
      label);

  const form = h("form", { novalidate: true, onsubmit: onIntroSubmit },
    h("div", { class: "field" },
      h("label", { for: "name-A" }, "First partner's name"),
      nameInput("A")),
    h("div", { class: "field" },
      h("label", { for: "name-B" }, "Second partner's name"),
      nameInput("B")),
    h("div", { class: "field" },
      h("label", { for: "country" }, "Country (optional)"),
      h("p", { class: "hint", id: "country-hint" },
        "Shows how partnered men and women there answered the same six survey questions."),
      countrySelect),
    h("fieldset", { class: "field" },
      h("legend", {}, "Which of you is the woman? (optional)"),
      h("p", { class: "hint" },
        "Only used to line your answers up with the survey's “the woman does it” figures."),
      womanOption("", "Prefer not to say / doesn't apply"),
      womanOption("A", womanLabelA),
      womanOption("B", womanLabelB)),
    errorBox(),
    h("button", { type: "submit", class: "primary" }, "Start"),
  );
  countrySelect.setAttribute("aria-describedby", "country-hint");

  return [
    h("h1", {}, "Who Does What"),
    h("p", {}, "Each of you says, separately, who does ten everyday household tasks. " +
      "Then you see where you agree and where you don't."),
    h("div", { class: "note" },
      h("h2", {}, "Privacy"),
      h("p", {}, "Nothing leaves this phone. Your answers are not saved or sent anywhere; " +
        "refreshing the page clears them.")),
    form,
  ];
}

function onIntroSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const nameA = form.elements["name-A"].value.trim() || "Partner A";
  const nameB = form.elements["name-B"].value.trim() || "Partner B";
  state.nameA = nameA;
  state.nameB = nameB;
  state.country = form.elements.country.value;
  state.womanIs = form.elements.woman.value;
  if (nameA === nameB) {
    state.error = "Please use two different names, so the results are clear.";
    render();
    app.querySelector("#name-B").focus();
    return;
  }
  go("answer-A");
}

function renderAnswers(who) {
  const mine = state.answers[who];
  const fieldset = (q, i) => {
    const legendId = `q-${q.id}-legend`;
    return h("fieldset", { class: "question", id: `q-${q.id}` },
      h("legend", { id: legendId }, h("span", { class: "qnum" }, `${i + 1}.`), " ", q.text),
      ANSWERS.map((a) =>
        h("label", { class: "choice" },
          h("input", {
            type: "radio",
            name: q.id,
            value: a.value,
            checked: mine[q.id] === a.value,
          }),
          a.label)),
    );
  };

  const issp = QUESTIONS.filter((q) => q.issp);
  const invisible = QUESTIONS.filter((q) => !q.issp);

  return [
    h("h1", {}, `${nameOf(who)}'s answers`),
    h("p", {}, `Answer on your own. ${nameOf(otherOf(who))} won't see these until you've both finished.`),
    h("p", { class: "hint" }, "“Me” means you, ", nameOf(who),
      "; “my partner” means ", nameOf(otherOf(who)), "."),
    h("form", { novalidate: true, onsubmit: (e) => onAnswersSubmit(e, who) },
      h("h2", {}, "Household tasks"),
      h("p", { class: "hint" }, "The same six questions as the ISSP 2022 survey: in your household, who does this?"),
      issp.map((q) => fieldset(q, QUESTIONS.indexOf(q))),
      h("h2", {}, "Invisible work"),
      h("p", { class: "hint" }, "Tasks that are easy to overlook. Not in the survey, so no country figures."),
      invisible.map((q) => fieldset(q, QUESTIONS.indexOf(q))),
      errorBox(),
      h("button", { type: "submit", class: "primary" },
        who === "A" ? "Done: hide my answers" : "Done: show our results"),
    ),
  ];
}

function onAnswersSubmit(e, who) {
  e.preventDefault();
  const form = e.target;
  const answers = {};
  const missing = [];
  for (const q of QUESTIONS) {
    const value = form.elements[q.id].value;
    if (value) answers[q.id] = value;
    else missing.push(q);
  }
  state.answers[who] = answers;
  if (missing.length) {
    const n = missing.length;
    state.error = `${n} question${n === 1 ? "" : "s"} still need${n === 1 ? "s" : ""} an answer: ` +
      missing.map((q) => q.text).join("; ") + ".";
    render();
    for (const q of missing) app.querySelector(`#q-${q.id}`).classList.add("missing");
    app.querySelector(`#q-${missing[0].id} input`).focus();
    return;
  }
  go(who === "A" ? "pass" : "reveal");
}

function renderPass() {
  return [
    h("h1", {}, `Pass the phone to ${state.nameB}`),
    h("p", {}, `${state.nameA}'s answers are hidden.`),
    h("p", {}, `${state.nameB}, answer the same questions on your own. ` +
      "You'll both see the results at the end."),
    h("button", { type: "button", class: "primary", onclick: () => go("answer-B") },
      `I'm ${state.nameB}: start`),
  ];
}

function countryLines(q, A, B) {
  if (!q.issp || !state.country || !countryData) return null;
  const c = countryData.countries[state.country];
  const t = c.tasks[q.id];
  if (t.men_pct === null || t.women_pct === null) {
    return h("p", { class: "country" },
      `Too few survey respondents in ${c.name} to show figures for this task.`);
  }
  const lines = [
    h("p", { class: "country" },
      `In ${c.name}, ${fmtPct(t.men_pct)} of partnered men and ${fmtPct(t.women_pct)} ` +
      "of partnered women say the woman always or usually does this."),
  ];
  if (state.womanIs) {
    const says = (who, pos) => {
      const w = womanDoesIt(pos, state.womanIs);
      if (w === null) return `${nameOf(who)}: a third person does it (left out of the survey figure)`;
      return `${nameOf(who)}: ${w ? "yes" : "no"}`;
    };
    lines.push(h("p", { class: "country" },
      "Does your answer count as “the woman does it”? ",
      `${says("A", A)}. ${says("B", B)}.`));
  }
  return lines;
}

function fmtPct(x) {
  return `${Math.round(x)}%`;
}

function renderReveal() {
  const rows = QUESTIONS.map((q) => {
    const A = toPosition(state.answers.A[q.id], "A");
    const B = toPosition(state.answers.B[q.id], "B");
    return { q, A, B, verdict: compare(A, B) };
  });
  const count = (v) => rows.filter((r) => r.verdict === v).length;

  const tagClass = { agree: "tag", "slightly different": "tag tag-slight", disagree: "tag tag-disagree" };
  const tagText = { agree: "Agree", "slightly different": "Slightly different", disagree: "Disagree" };

  const card = ({ q, A, B, verdict }) =>
    h("li", { class: "card" },
      h("div", { class: "card-head" },
        h("h3", {}, q.text),
        h("span", { class: tagClass[verdict] }, tagText[verdict])),
      h("dl", {},
        h("div", {}, h("dt", {}, `${state.nameA} says`),
          h("dd", {}, describePosition(A, state.nameA, state.nameB))),
        h("div", {}, h("dt", {}, `${state.nameB} says`),
          h("dd", {}, describePosition(B, state.nameA, state.nameB)))),
      countryLines(q, A, B));

  const country = state.country && countryData ? countryData.countries[state.country] : null;

  return [
    h("h1", {}, "Your results"),
    h("p", { class: "summary" },
      `Agree on ${count("agree")}, slightly different on ${count("slightly different")}, ` +
      `disagree on ${count("disagree")} of ${rows.length} tasks.`),
    h("p", { class: "hint" },
      "“Slightly different” means one step apart, for example “usually” vs “always”, " +
      "or “about equal” vs “usually”. Two or more steps apart is “disagree”."),
    h("h2", {}, "Household tasks"),
    h("ul", { class: "cards" }, rows.filter((r) => r.q.issp).map(card)),
    h("h2", {}, "Invisible work"),
    h("ul", { class: "cards" }, rows.filter((r) => !r.q.issp).map(card)),
    country
      ? h("p", { class: "hint" },
          `Country figures: ISSP 2022 (ZA10000 v2.0.0), weighted, ${country.name}. ` +
          "Men and women in the survey come from different households, so the figures " +
          "compare how men and women describe their homes, not couples' agreement. " +
          "Answers of “done by a third person” are left out.")
      : null,
    h("button", {
      type: "button",
      class: "secondary",
      onclick: () => { state = freshState(); render(); },
    }, "Start over (clears all answers)"),
  ];
}

// --- Start -----------------------------------------------------------------
// The country file is fetched once, from this app's own folder, before any
// choice is made, so the request reveals nothing about what you pick.
async function start() {
  try {
    const res = await fetch("data/country_tasks.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    countryData = await res.json();
  } catch {
    countryData = null; // the tool still works, just without country figures
  }
  render();
}

start();
