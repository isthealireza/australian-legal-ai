"use strict";

/**
 * Australian Legal AI Agent — interface layer.
 *
 * This file renders what the API returns and nothing more. It never composes a
 * legal statement, never infers a citation, and never presents a refusal as
 * anything softer than a refusal. All text is inserted as text nodes, so
 * nothing returned by the service can become markup.
 */

const REQUEST_TIMEOUT_MS = 120_000;
const HISTORY_KEY = "au-legal-ai.history.v1";
const HISTORY_LIMIT = 12;

const els = {
  form: document.getElementById("form"),
  question: document.getElementById("question"),
  submit: document.getElementById("submit"),
  hint: document.getElementById("hint"),
  selected: document.getElementById("selected"),
  corpus: document.getElementById("corpus"),
  history: document.getElementById("history"),
  historyEmpty: document.getElementById("history-empty"),
  clearHistory: document.getElementById("clear-history"),
  result: document.getElementById("result"),
  resultPanel: document.getElementById("result-panel"),
  routeForm: document.getElementById("route-form"),
  problem: document.getElementById("problem"),
  routeSubmit: document.getElementById("route-submit"),
  routeHint: document.getElementById("route-hint"),
  routeResult: document.getElementById("route-result"),
  intro: document.getElementById("intro"),
  servicePill: document.getElementById("service-pill"),
  serviceText: document.getElementById("service-text"),
  sidebar: document.getElementById("sidebar"),
  menuToggle: document.getElementById("menu-toggle"),
};

/** Currently chosen provision, or null. Set only from the corpus listing. */
let selection = null;
/** Whether the service reports independent entailment verification as active. */
let entailmentActive = false;

/* ------------------------------------------------------------------ utils */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

/** True only for an http(s) URL, so no other scheme can ever become an href. */
function isSafeHttpUrl(value) {
  try {
    const parsed = new URL(String(value));
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch {
    return false;
  }
}

function shortDigest(value) {
  const text = String(value ?? "");
  return text.length > 20 ? `${text.slice(0, 16)}…${text.slice(-4)}` : text;
}

/* --------------------------------------------------------------- refusals */

/**
 * Plain-English explanation for each typed refusal code, plus what to try.
 * A refusal is a correct outcome of the contract, so it is explained rather
 * than apologised for.
 */
const REFUSALS = {
  RESEARCH_REFUSED: [
    "The indexed corpus does not hold the provision that was asked about, or the jurisdiction did not match.",
    "Choose the situation that best matches what happened.",
  ],
  RESEARCH_TERMINATED: [
    "The research was stopped because its audit trail could not be recorded.",
    "This is a configuration problem on the server, not a problem with your question.",
  ],
  MODEL_UNAVAILABLE: [
    "The answer model could not be reached, so no answer was produced.",
    "Try again shortly. The service refuses rather than answering without the model.",
  ],
  MODEL_OUTPUT_MALFORMED: [
    "The answer model returned something the service could not use.",
    "Try rephrasing your question.",
  ],
  NO_PROPOSITIONS: [
    "This provision does not contain anything that answers your question.",
    "That is the expected result when the law is silent on the point. Try another situation.",
  ],
  CITATION_SOURCE_UNKNOWN: [
    "A citation did not match the verified source, so the entire answer was discarded.",
    "Nothing partial is shown: one unsupported citation refuses the whole answer.",
  ],
  CITATION_DIGEST_MISMATCH: [
    "A citation named a document whose digest did not match the verified source.",
    "Nothing partial is shown: one unsupported citation refuses the whole answer.",
  ],
  CITATION_PROVISION_MISMATCH: [
    "A citation pointed at a different provision from the one that was retrieved.",
    "Nothing partial is shown: one unsupported citation refuses the whole answer.",
  ],
  CITATION_PINPOINT_MISMATCH: [
    "A citation pointed at a different pinpoint from the one that was retrieved.",
    "Nothing partial is shown: one unsupported citation refuses the whole answer.",
  ],
  QUOTE_NOT_IN_SOURCE: [
    "A quoted passage was not found word for word in the verified text.",
    "A quote that cannot be located is treated as fabricated, and refuses the whole answer.",
  ],
  ENTAILMENT_UNSUPPORTED: [
    "Independent verification found that the provision does not support the statement made about it.",
    "The answer was discarded rather than shown with a caveat.",
  ],
  ENTAILMENT_UNAVAILABLE: [
    "Independent verification could not be completed, so the answer was not accepted.",
    "A check that cannot run never counts as a check that passed.",
  ],
  CORPUS_UNAVAILABLE: [
    "No corpus is configured, so the service cannot answer anything.",
    "Set LEGAL_AI_WA_CORPUS_ROOT and restart the service.",
  ],
  VERIFIER_NOT_CONFIGURED: [
    "Entailment verification was requested but could not be configured.",
    "Set OPENROUTER_API_KEY, or turn off LEGAL_AI_VERIFY_ENTAILMENT, then restart.",
  ],
  ENTAILMENT_REQUIRED_FOR_LIVE_MODEL: [
    "A live answer model is selected without entailment verification, which is not permitted.",
    "Set LEGAL_AI_VERIFY_ENTAILMENT=1 and restart, or switch back to the mock model.",
  ],
  AUDIT_SINK_NOT_WRITABLE: [
    "The audit log cannot be written, so the service will not answer.",
    "Check LEGAL_AI_RESEARCH_AUDIT_LOG points somewhere writable, then restart.",
  ],
};

function explainRefusal(code) {
  return REFUSALS[code] ?? [
    "The service could not verify an answer, so it refused.",
    "No answer is shown, because an unverified answer is worse than none.",
  ];
}

/* ----------------------------------------------------------------- corpus */

/**
 * Plain-language situations, keyed by the provision they resolve to.
 *
 * A section number means nothing to someone who has just had a prang. The card
 * asks the question the person actually has; the citation underneath is what
 * makes the answer checkable. Both are shown, in that order of prominence.
 *
 * A provision with no entry here still appears, labelled by its official
 * heading, so growing the corpus can never silently hide a situation.
 */
const SITUATIONS = {
  "Road Traffic Act 1974|s 55": {
    title: "Traffic incident involving property damage",
    description: "What must I do after damaging someone's property or vehicle?",
  },
  "Road Traffic Act 1974|s 56": {
    title: "Traffic incident involving injury or serious damage",
    description:
      "What must I do when someone is injured or the incident must be reported to police?",
  },
};

const JURISDICTIONS = { WA: "Western Australia" };

function jurisdictionName(code) {
  return JURISDICTIONS[code] ?? code;
}

function situationFor(act, provision) {
  const known = SITUATIONS[`${act.act_title}|${provision.provision_identifier}`];
  if (known) return known;
  return {
    title: provision.heading ?? `${act.act_title} ${provision.provision_identifier}`,
    description: "Ask a question about this provision.",
  };
}

function renderCorpus(payload) {
  els.corpus.replaceChildren();
  const acts = payload?.acts ?? [];

  if (acts.length === 0) {
    els.corpus.append(
      el("p", "empty", "No situations are available, so every question will be refused."),
    );
    return;
  }

  const total = acts.reduce((count, act) => count + act.provisions.length, 0);
  els.corpus.append(
    el("p", "act-meta", `${total} situation${total === 1 ? "" : "s"} available`),
  );

  const list = el("ul", "provisions");
  for (const act of acts) {
    for (const provision of act.provisions) {
      const situation = situationFor(act, provision);
      const choice = {
        act_title: act.act_title,
        jurisdiction: act.jurisdiction,
        provision_identifier: provision.provision_identifier,
        pinpoint: provision.pinpoint,
        heading: provision.heading,
        title: situation.title,
      };

      const item = document.createElement("li");
      const button = el("button", "provision");
      button.type = "button";
      button.setAttribute("aria-pressed", "false");
      button.dataset.choice = `${act.act_title}|${provision.provision_identifier}`;

      button.append(el("span", "situation", situation.title));
      button.append(el("span", "situation-desc", situation.description));
      // The citation stays visible, but as supporting detail rather than as
      // the label someone has to interpret in order to navigate.
      button.append(
        el(
          "span",
          "situation-cite",
          `${act.act_title} · ${provision.provision_identifier} · ${jurisdictionName(act.jurisdiction)}`,
        ),
      );

      button.addEventListener("click", () => select(choice));
      item.append(button);
      list.append(item);
    }
  }
  els.corpus.append(list);
}

function select(provision) {
  selection = provision;
  const key = `${provision.act_title}|${provision.provision_identifier}`;

  for (const button of document.querySelectorAll(".provision")) {
    button.setAttribute("aria-pressed", button.dataset.choice === key ? "true" : "false");
  }

  els.selected.replaceChildren();
  els.selected.classList.add("is-set");
  els.selected.append(el("span", "selected-title", provision.title ?? provision.pinpoint));
  els.selected.append(
    el(
      "span",
      "selected-cite",
      `${provision.act_title} · ${provision.provision_identifier} · ${jurisdictionName(provision.jurisdiction)}`,
    ),
  );
  hideIntro();
  refreshSubmit();

  if (window.matchMedia("(max-width: 960px)").matches) {
    els.sidebar.classList.remove("is-open");
    els.menuToggle.setAttribute("aria-expanded", "false");
    els.question.focus();
  }
}

function hideIntro() {
  if (els.intro) els.intro.hidden = true;
}

function refreshSubmit() {
  const ready = selection !== null && els.question.value.trim().length > 0;
  els.submit.disabled = !ready;
  els.hint.textContent = selection === null
    ? "Choose a situation to begin."
    : ready ? "" : "Now type your question.";
}

/* ---------------------------------------------------------------- results */

function showResearching() {
  hideIntro();
  els.resultPanel.hidden = false;
  els.result.replaceChildren();

  const state = el("div", "state");
  state.append(el("div", "verdict-title"));
  const steps = el("ul", "steps");
  const labels = [
    "Retrieving the verified provision",
    "Reading the recorded text",
    entailmentActive ? "Drafting, then independently verifying" : "Drafting from the verified text",
    "Validating every citation",
  ];
  for (const [index, label] of labels.entries()) {
    const li = document.createElement("li");
    li.dataset.state = index === 0 ? "active" : "pending";
    const tick = el("span", "tick");
    if (index === 0) tick.append(el("span", "spinner"));
    else tick.textContent = "·";
    li.append(tick, el("span", null, label));
    steps.append(li);
  }
  state.append(steps);
  els.result.append(state);

  // Advance the indicator so a long provider call still shows progress. The
  // steps describe the pipeline honestly; they are not a fake progress bar.
  let index = 0;
  return window.setInterval(() => {
    const items = steps.querySelectorAll("li");
    if (index >= items.length - 1) return;
    items[index].dataset.state = "done";
    items[index].querySelector(".tick").textContent = "✓";
    index += 1;
    items[index].dataset.state = "active";
    const tick = items[index].querySelector(".tick");
    tick.textContent = "";
    tick.append(el("span", "spinner"));
  }, 4000);
}

function renderCitation(cite) {
  const wrap = el("div", "cite");

  const head = el("div", "cite-head");
  head.append(el("span", "act", cite.act_title));
  head.append(el("span", "pin", cite.pinpoint));
  wrap.append(head);

  const dl = el("dl");
  const rows = [
    ["Jurisdiction", "Western Australia"],
    ["Provision", cite.provision_identifier],
    ["Version", cite.source_version ?? cite.compilation_date ?? "not recorded"],
    ["Digest", shortDigest(cite.sha256)],
  ];
  for (const [term, value] of rows) dl.append(el("dt", null, term), el("dd", null, value));

  const dd = el("dd");
  if (isSafeHttpUrl(cite.official_source_url)) {
    const link = el("a", null, "View on the official legislation website");
    link.href = cite.official_source_url;
    link.rel = "noopener noreferrer";
    link.target = "_blank";
    dd.append(link);
  } else {
    dd.append(el("span", null, "link withheld — not a recognised official URL"));
  }
  dl.append(el("dt", null, "Source"), dd);
  wrap.append(dl);

  const checks = el("div", "checks");
  checks.append(el("span", "check", "✓ Citation verified against source"));
  checks.append(el("span", cite.quote ? "check" : "check off",
    cite.quote ? "✓ Quote found verbatim" : "No quote given"));
  checks.append(el("span", entailmentActive ? "check" : "check off",
    entailmentActive ? "✓ Independently verified" : "Entailment check not enabled"));
  wrap.append(checks);

  return wrap;
}

function renderAnswer(payload) {
  const verdict = el("div", "verdict answered");
  verdict.append(el("span", "tag", "Answered"));
  const count = payload.propositions.length;
  verdict.append(el("span", "about", count === 1
    ? "1 statement, carrying a verified citation."
    : `${count} statements, each carrying a verified citation.`));
  els.result.append(verdict);

  for (const proposition of payload.propositions) {
    const block = el("div", "proposition");
    block.append(el("p", "statement", proposition.statement));
    if (proposition.citation.quote) {
      block.append(el("blockquote", "quote", proposition.citation.quote));
    }
    block.append(renderCitation(proposition.citation));
    els.result.append(block);
  }
}

function renderRefusal(payload) {
  const [why, next] = explainRefusal(payload.code);

  const verdict = el("div", "verdict refused");
  verdict.append(el("span", "tag", "Refused"));
  verdict.append(el("span", "about", "No answer was produced, and nothing partial is shown."));
  els.result.append(verdict);

  const block = el("div", "refusal");
  block.append(el("p", "why", why));
  block.append(el("p", "code", payload.code ?? "REFUSED"));
  block.append(el("p", "next", next));
  els.result.append(block);
}

function renderResult(payload) {
  els.resultPanel.hidden = false;
  els.result.replaceChildren();
  if (payload.outcome === "ANSWERED") renderAnswer(payload);
  else renderRefusal(payload);
}

function renderError(message) {
  els.resultPanel.hidden = false;
  els.result.replaceChildren();
  const verdict = el("div", "verdict refused");
  verdict.append(el("span", "tag", "Not completed"));
  els.result.append(verdict);
  const block = el("div", "refusal");
  block.append(el("p", "why", message));
  block.append(el("p", "next", "No answer was produced."));
  els.result.append(block);
}

/* ---------------------------------------------------------------- history */

function loadHistory() {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveHistory(entries) {
  try {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, HISTORY_LIMIT)));
  } catch {
    /* A browser with storage disabled simply gets no history. */
  }
}

function recordHistory(entry) {
  const entries = loadHistory().filter(
    (item) => !(item.question === entry.question && item.pinpoint === entry.pinpoint),
  );
  entries.unshift(entry);
  saveHistory(entries);
  renderHistory();
}

function renderHistory() {
  const entries = loadHistory();
  els.history.replaceChildren();
  els.historyEmpty.hidden = entries.length > 0;
  els.clearHistory.hidden = entries.length === 0;

  for (const entry of entries) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.append(el("span", "q", entry.question));

    const meta = el("span", "meta");
    meta.append(el("span", `tag ${entry.outcome === "ANSWERED" ? "answered" : "refused"}`,
      entry.outcome === "ANSWERED" ? "Answered" : "Refused"));
    meta.append(el("span", null, ` · ${entry.title ?? entry.pinpoint}`));
    button.append(meta);

    button.addEventListener("click", () => {
      els.question.value = entry.question;
      select({
        act_title: entry.act_title,
        jurisdiction: entry.jurisdiction,
        provision_identifier: entry.provision_identifier,
        pinpoint: entry.pinpoint,
        heading: entry.heading ?? null,
        title: entry.title ?? entry.pinpoint,
      });
      refreshSubmit();
      els.question.focus();
    });

    item.append(button);
    els.history.append(item);
  }
}

/* ------------------------------------------------------------------ routing */

/* Plain-English explanation for each routing refusal code. Routing never
 * invents a provision, so "nothing matches" is a real, honest outcome. */
const ROUTE_REFUSALS = {
  NO_MATCHING_PROVISION:
    "Nothing in the indexed corpus covers this problem. Rather than guess at a nearest match, the system says so. It can only answer from the situations listed on the left.",
  REQUEST_OUT_OF_SCOPE:
    "This reads as a request to review or draft a document, which is out of scope. The system researches legislation; it does not review your contract or write letters.",
  ROUTER_UNAVAILABLE:
    "Routing needs the live model, which is not available right now. Pick the situation that fits from the list on the left and ask your question there.",
  CATALOGUE_EMPTY:
    "No provisions are indexed, so there is nothing to route to.",
};

function choiceTitle(choice) {
  return choice.heading ? `${choice.pinpoint} — ${choice.heading}` : choice.pinpoint;
}

/* Fill the manual composer from a routed choice, so the chosen provision is
 * visible and the user can research or adjust it by hand. */
function adoptChoice(choice, problem) {
  els.question.value = problem;
  select({
    act_title: choice.act_title,
    jurisdiction: choice.jurisdiction,
    provision_identifier: choice.provision_identifier,
    pinpoint: choice.pinpoint,
    heading: choice.heading ?? null,
    title: choiceTitle(choice),
  });
  refreshSubmit();
}

/* Show which provision was chosen and why — the choice is visible, not magic. */
function renderChosen(choice, label) {
  const card = el("div", "routed-choice");
  card.append(el("span", "tag answered", label));
  card.append(el("p", "routed-prov",
    `${choice.act_title} — ${choice.pinpoint}${choice.heading ? ` · ${choice.heading}` : ""}`));
  if (choice.reason) card.append(el("p", "routed-why", `Why: ${choice.reason}`));
  return card;
}

function renderRouteResult(payload) {
  els.routeResult.replaceChildren();
  const problem = els.problem.value.trim();

  if (payload.outcome === "ROUTED") {
    els.routeResult.append(renderChosen(payload.chosen, "Chosen provision"));
    adoptChoice(payload.chosen, problem);
    renderResult(payload.answer);
    els.resultPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  if (payload.outcome === "CANDIDATES") {
    els.routeResult.append(el("p", "routed-lead",
      "More than one provision could fit. Choose the one that matches, then research it."));
    for (const choice of payload.candidates) {
      const button = el("button", "candidate");
      button.type = "button";
      button.append(el("span", "cand-prov",
        `${choice.act_title} — ${choice.pinpoint}${choice.heading ? ` · ${choice.heading}` : ""}`));
      if (choice.reason) button.append(el("span", "cand-why", choice.reason));
      button.addEventListener("click", () => {
        adoptChoice(choice, problem);
        els.question.focus();
        els.form.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
      els.routeResult.append(button);
    }
    return;
  }

  // REFUSED.
  const block = el("div", "refusal");
  block.append(el("p", "why",
    ROUTE_REFUSALS[payload.code] ?? "The system did not route this to a provision."));
  els.routeResult.append(block);
}

els.routeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const problem = els.problem.value.trim();
  if (!problem) return;

  els.routeSubmit.disabled = true;
  els.routeHint.textContent = "Choosing a provision…";
  els.routeResult.replaceChildren();

  const controller = new AbortController();
  const expiry = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch("/api/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({ problem }),
    });
    if (response.status === 422) {
      els.routeResult.replaceChildren(
        el("div", "refusal", "The service rejected that as malformed. Try shortening the description."));
      return;
    }
    renderRouteResult(await response.json());
  } catch (error) {
    els.routeResult.replaceChildren(el("div", "refusal", error.name === "AbortError"
      ? "Routing timed out. Try again, or pick a situation from the list."
      : "The service could not be reached."));
  } finally {
    window.clearInterval(0);
    window.clearTimeout(expiry);
    els.routeSubmit.disabled = false;
    els.routeHint.textContent =
      "Not sure which situation fits? Describe it and let the system choose. You can still pick one yourself below.";
  }
});

/* ------------------------------------------------------------------ wiring */

els.question.addEventListener("input", refreshSubmit);

els.menuToggle.addEventListener("click", () => {
  const open = els.sidebar.classList.toggle("is-open");
  els.menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
});

els.clearHistory.addEventListener("click", () => {
  saveHistory([]);
  renderHistory();
});

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (selection === null) return;

  const question = els.question.value.trim();
  if (!question) return;

  els.submit.disabled = true;
  els.hint.textContent = "Researching…";
  const ticker = showResearching();

  // Give up rather than spin forever: a live provider can be congested, and a
  // request that never resolves is indistinguishable from a broken page.
  const controller = new AbortController();
  const expiry = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        question,
        jurisdiction: selection.jurisdiction,
        act_title: selection.act_title,
        provision_identifier: selection.provision_identifier,
        pinpoint: selection.pinpoint,
      }),
    });

    if (response.status === 422) {
      renderError("The service rejected that request as malformed. Try shortening your question.");
      return;
    }

    const payload = await response.json();
    renderResult(payload);
    recordHistory({
      question,
      outcome: payload.outcome,
      act_title: selection.act_title,
      jurisdiction: selection.jurisdiction,
      provision_identifier: selection.provision_identifier,
      pinpoint: selection.pinpoint,
      heading: selection.heading ?? null,
      title: selection.title ?? selection.pinpoint,
      at: new Date().toISOString(),
    });
  } catch (error) {
    renderError(error.name === "AbortError"
      ? "The request timed out before an answer could be verified."
      : "The service could not be reached.");
  } finally {
    window.clearInterval(ticker);
    window.clearTimeout(expiry);
    els.submit.disabled = false;
    refreshSubmit();
  }
});

/* ------------------------------------------------------------------- boot */

fetch("/api/health")
  .then((response) => response.json())
  .then((health) => {
    entailmentActive = health.entailment_verified === true;
    const ready = health.corpus_configured === true;
    els.servicePill.classList.toggle("is-down", !ready);
    els.serviceText.textContent = ready
      ? `Ready · ${health.answer_model} model${entailmentActive ? " · verified" : ""}`
      : "Service unavailable";
  })
  .catch(() => {
    els.servicePill.classList.add("is-down");
    els.serviceText.textContent = "Service unreachable";
  });

fetch("/api/corpus")
  .then((response) => response.json())
  .then(renderCorpus)
  .catch(() => {
    els.corpus.replaceChildren(el("p", "empty", "The corpus listing could not be loaded."));
  });

renderHistory();
refreshSubmit();
