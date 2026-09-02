"use strict";

const REQUEST_TIMEOUT_MS = 90_000;

const form = document.getElementById("form");
const submit = document.getElementById("submit");
const result = document.getElementById("result");
const statusLine = document.getElementById("status");

/** True only for an http(s) URL, so no other scheme can become an href. */
function isSafeHttpUrl(value) {
  try {
    const parsed = new URL(String(value));
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch (error) {
    return false;
  }
}

/** Build an element with text content, avoiding any HTML interpolation. */
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** Render one validated citation as a definition list. */
function citation(cite) {
  const wrap = el("div", "cite");
  const dl = el("dl");
  const rows = [
    ["Act", cite.act_title],
    ["Provision", cite.pinpoint],
    ["Version", cite.source_version || cite.compilation_date || "not recorded"],
    ["Digest", cite.sha256],
  ];
  for (const [term, value] of rows) {
    dl.append(el("dt", null, term), el("dd", null, String(value)));
  }
  // The server only ever emits an allowlisted HTTPS legislation URL, but the
  // scheme is re-checked here so nothing else could ever become a live href.
  const dd = el("dd");
  if (isSafeHttpUrl(cite.official_source_url)) {
    const link = el("a", null, cite.official_source_url);
    link.href = cite.official_source_url;
    link.rel = "noopener noreferrer";
    link.target = "_blank";
    dd.append(link);
  } else {
    dd.append(el("span", null, `${cite.official_source_url} (link withheld)`));
  }
  dl.append(el("dt", null, "Source"), dd);
  wrap.append(dl);
  if (cite.quote) {
    const quote = el("blockquote", "code", cite.quote);
    wrap.append(quote);
  }
  return wrap;
}

/** Render whatever the API returned. A refusal is shown as a refusal. */
function render(payload) {
  result.replaceChildren();
  const answered = payload.outcome === "ANSWERED";
  const card = el("div", `card ${answered ? "answered" : "refused"}`);
  card.append(el("div", "badge", answered ? "Answered — fully cited" : "Refused"));

  if (answered) {
    for (const proposition of payload.propositions) {
      card.append(el("p", "statement", proposition.statement));
      card.append(citation(proposition.citation));
    }
  } else {
    card.append(el("p", "statement",
      "The system could not verify an answer from its indexed corpus, so it refused."));
    card.append(el("p", "code", payload.code));
  }
  result.append(card);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submit.disabled = true;
  result.replaceChildren(el("p", null, "Researching\u2026"));
  const body = Object.fromEntries(new FormData(form).entries());
  // Give up rather than spin forever: a live provider can be congested, and a
  // request that never resolves is indistinguishable from a broken page.
  const controller = new AbortController();
  const expiry = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    render(await response.json());
  } catch (error) {
    const message = error.name === "AbortError"
      ? "The request timed out before an answer could be verified. No answer was produced."
      : "The service could not be reached. No answer was produced.";
    result.replaceChildren(el("div", "card refused", message));
  } finally {
    clearTimeout(expiry);
    submit.disabled = false;
  }
});

fetch("/api/health")
  .then((response) => response.json())
  .then((health) => {
    statusLine.textContent = health.corpus_configured
      ? `Service ready \u2014 answer model: ${health.answer_model}.`
      : "No corpus is configured, so every request will be refused.";
  })
  .catch(() => {
    statusLine.textContent = "Service status unavailable.";
  });
