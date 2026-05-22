const PROFICIENCY = [
  null,
  { label: "Very Unfamiliar", className: "level-1" },
  { label: "Unfamiliar", className: "level-2" },
  { label: "So-so", className: "level-3" },
  { label: "Familiar", className: "level-4" },
  { label: "Very Familiar", className: "level-5" },
];

const REGION_LABELS = {
  頭部: "Head",
  腹腔: "Abdomen",
  骨盆會陰: "Pelvis and Perineum",
  下肢: "Lower Limb",
};

const CATEGORY_LABELS = {
  "咀嚼、表情肌": "Mastication and Facial Muscles",
  眼外肌: "Extraocular Muscles",
  總頸動脈及分支: "Common Carotid and Branches",
  靜脈: "Veins",
  腦神經及分支: "Cranial Nerves and Branches",
  "神經節、腺體": "Ganglia and Glands",
  肌肉: "Muscles",
  動脈: "Arteries",
  神經: "Nerves",
  臟器: "Organs",
  "臟器、其他": "Organs and Other Structures",
  其他: "Other Structures",
  大腿肌肉: "Thigh Muscles",
  小腿肌肉: "Leg Muscles",
  腳掌肌肉: "Foot Muscles",
  "韌帶、膝蓋": "Ligaments and Knee",
};

const DEFAULT_LEVEL = 3;
const STORAGE_KEY = "anatomy-proficiency-v1";

const state = {
  terms: [],
  filtered: [],
  currentIndex: 0,
  view: "home",
  proficiency: JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"),
  quiz: {
    current: null,
    answered: false,
    correct: 0,
    total: 0,
  },
};

const els = {
  homeView: document.querySelector("#homeView"),
  wordBankView: document.querySelector("#wordBankView"),
  testView: document.querySelector("#testView"),
  mistakeView: document.querySelector("#mistakeView"),
  coverageText: document.querySelector("#coverageText"),
  bankCountText: document.querySelector("#bankCountText"),
  searchInput: document.querySelector("#searchInput"),
  regionSelect: document.querySelector("#regionSelect"),
  imageOnlyToggle: document.querySelector("#imageOnlyToggle"),
  totalCount: document.querySelector("#totalCount"),
  regionCount: document.querySelector("#regionCount"),
  imageCount: document.querySelector("#imageCount"),
  termList: document.querySelector("#termList"),
  shuffleButton: document.querySelector("#shuffleButton"),
  prevButton: document.querySelector("#prevButton"),
  nextButton: document.querySelector("#nextButton"),
  imageFrame: document.querySelector("#imageFrame"),
  termTitle: document.querySelector("#termTitle"),
  regionBadge: document.querySelector("#regionBadge"),
  categoryBadge: document.querySelector("#categoryBadge"),
  quizImage: document.querySelector("#quizImage"),
  quizRegionBadge: document.querySelector("#quizRegionBadge"),
  quizCategoryBadge: document.querySelector("#quizCategoryBadge"),
  quizScore: document.querySelector("#quizScore"),
  options: document.querySelector("#options"),
  testFeedback: document.querySelector("#testFeedback"),
  nextQuizButton: document.querySelector("#nextQuizButton"),
  mistakeSummary: document.querySelector("#mistakeSummary"),
  mistakeList: document.querySelector("#mistakeList"),
  clearMistakesButton: document.querySelector("#clearMistakesButton"),
};

function translateRegion(region) {
  return REGION_LABELS[region] || region || "General";
}

function translateCategory(category) {
  return CATEGORY_LABELS[category] || category || "Terms";
}

function clampLevel(level) {
  return Math.min(5, Math.max(1, level));
}

function recordFor(term) {
  const existing = state.proficiency[term.id];
  if (existing && typeof existing === "object") {
    return {
      level: clampLevel(Number(existing.level) || DEFAULT_LEVEL),
      attempts: Number(existing.attempts) || 0,
      mistakes: Number(existing.mistakes) || 0,
      lastResult: existing.lastResult || null,
      lastWrong: existing.lastWrong || null,
      lastAt: existing.lastAt || null,
    };
  }
  return {
    level: DEFAULT_LEVEL,
    attempts: 0,
    mistakes: 0,
    lastResult: null,
    lastWrong: null,
    lastAt: null,
  };
}

function saveProficiency() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.proficiency));
}

function proficiencyBadge(record) {
  const level = clampLevel(record.level);
  const meta = PROFICIENCY[level];
  return `<span class="proficiency ${meta.className}">${meta.label}</span>`;
}

function updateProficiency(term, correct, chosenTerm) {
  const record = recordFor(term);
  record.level = clampLevel(record.level + (correct ? 1 : -1));
  record.attempts += 1;
  record.lastResult = correct ? "correct" : "wrong";
  record.lastAt = new Date().toISOString();
  if (!correct) {
    record.mistakes += 1;
    record.lastWrong = chosenTerm.term;
  }
  state.proficiency[term.id] = record;
  saveProficiency();
  return record;
}

function hasImage(term) {
  return term.status === "downloaded" && term.image;
}

function displayImage(container, term) {
  container.replaceChildren();
  if (hasImage(term)) {
    const img = document.createElement("img");
    img.src = term.image;
    img.alt = term.term;
    img.loading = "eager";
    img.addEventListener("error", () => {
      container.innerHTML = `<div class="placeholder"><strong>${term.term}</strong><span>Image file not available</span></div>`;
    });
    container.append(img);
    return;
  }
  container.innerHTML = `<div class="placeholder"><strong>${term.term}</strong><span>No local image</span></div>`;
}

function currentTerm() {
  return state.filtered[state.currentIndex] || state.filtered[0] || null;
}

function setView(view) {
  state.view = view;
  els.homeView.classList.toggle("active", view === "home");
  els.wordBankView.classList.toggle("active", view === "wordBank");
  els.testView.classList.toggle("active", view === "test");
  els.mistakeView.classList.toggle("active", view === "mistakes");
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  if (view === "wordBank") {
    renderAll();
  }
  if (view === "test") {
    nextQuizQuestion();
  }
  if (view === "mistakes") {
    renderMistakes();
  }
}

function applyFilters() {
  const query = els.searchInput.value.trim().toLowerCase();
  const region = els.regionSelect.value;
  const imageOnly = els.imageOnlyToggle.checked;

  state.filtered = state.terms.filter((term) => {
    const searchable = [
      term.term,
      term.raw,
      translateRegion(term.region),
      translateCategory(term.category),
    ]
      .join(" ")
      .toLowerCase();
    const matchesQuery = !query || searchable.includes(query);
    const matchesRegion = !region || term.region === region;
    const matchesImage = !imageOnly || hasImage(term);
    return matchesQuery && matchesRegion && matchesImage;
  });

  if (state.currentIndex >= state.filtered.length) {
    state.currentIndex = 0;
  }
  renderAll();
}

function renderStats() {
  const images = state.terms.filter(hasImage).length;
  const regions = new Set(state.terms.map((term) => term.region)).size;
  els.totalCount.textContent = String(state.filtered.length);
  els.regionCount.textContent = String(regions);
  els.imageCount.textContent = String(images);
  els.coverageText.textContent = `${state.terms.length} terms, ${images} local images`;
  els.bankCountText.textContent = `${state.filtered.length} shown from ${state.terms.length}`;
}

function renderRegions() {
  const regions = Array.from(new Set(state.terms.map((term) => term.region))).filter(Boolean);
  els.regionSelect.innerHTML = `<option value="">All regions</option>`;
  for (const region of regions) {
    const option = document.createElement("option");
    option.value = region;
    option.textContent = translateRegion(region);
    els.regionSelect.append(option);
  }
}

function thumbnail(term) {
  if (!hasImage(term)) {
    return `<span class="term-thumb placeholder-thumb"></span>`;
  }
  return `<img class="term-thumb" src="${term.image}" alt="" loading="lazy" />`;
}

function renderList() {
  const fragment = document.createDocumentFragment();
  state.filtered.forEach((term, index) => {
    const button = document.createElement("button");
    button.className = `term-item ${index === state.currentIndex ? "active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      ${thumbnail(term)}
      <span>
        <strong>${term.term}</strong>
        <span>${translateRegion(term.region)} · ${translateCategory(term.category)}</span>
      </span>
    `;
    button.addEventListener("click", () => {
      state.currentIndex = index;
      renderAll();
      focusStudyOnMobile();
    });
    fragment.append(button);
  });
  els.termList.replaceChildren(fragment);
}

function focusStudyOnMobile() {
  if (state.view !== "wordBank" || !window.matchMedia("(max-width: 980px)").matches) {
    return;
  }
  const root = document.scrollingElement || document.documentElement;
  root.scrollTop = 0;
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}

function renderStudy() {
  const term = currentTerm();
  if (!term) {
    els.termTitle.textContent = "No matching terms";
    els.regionBadge.textContent = "Word Bank";
    els.categoryBadge.textContent = "Try another search";
    els.imageFrame.innerHTML = `<div class="placeholder"><strong>No matching terms</strong></div>`;
    return;
  }

  displayImage(els.imageFrame, term);
  els.termTitle.textContent = term.term;
  els.regionBadge.textContent = translateRegion(term.region);
  els.categoryBadge.textContent = translateCategory(term.category);
}

function shuffleTerms() {
  for (let i = state.filtered.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [state.filtered[i], state.filtered[j]] = [state.filtered[j], state.filtered[i]];
  }
  state.currentIndex = 0;
  renderAll();
}

function move(delta) {
  if (!state.filtered.length) {
    return;
  }
  state.currentIndex = (state.currentIndex + delta + state.filtered.length) % state.filtered.length;
  renderAll();
}

function sampleOptions(answer) {
  const pool = state.terms.filter((term) => term.id !== answer.id);
  const sameRegion = pool.filter((term) => term.region === answer.region);
  const source = sameRegion.length >= 3 ? sameRegion : pool;
  const picks = [];
  while (picks.length < 3 && source.length) {
    const candidate = source[Math.floor(Math.random() * source.length)];
    if (!picks.some((term) => term.id === candidate.id)) {
      picks.push(candidate);
    }
  }
  const options = [answer, ...picks];
  for (let i = options.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [options[i], options[j]] = [options[j], options[i]];
  }
  return options;
}

function nextQuizQuestion() {
  const pool = state.terms.filter(hasImage);
  if (!pool.length) {
    els.quizImage.innerHTML = `<div class="placeholder"><strong>No quiz images</strong></div>`;
    els.options.replaceChildren();
    return;
  }
  state.quiz.current = pool[Math.floor(Math.random() * pool.length)];
  state.quiz.answered = false;
  els.testFeedback.hidden = true;
  els.testFeedback.replaceChildren();
  displayImage(els.quizImage, state.quiz.current);
  els.quizRegionBadge.textContent = translateRegion(state.quiz.current.region);
  els.quizCategoryBadge.textContent = translateCategory(state.quiz.current.category);
  els.quizScore.textContent = `${state.quiz.correct} / ${state.quiz.total}`;
  renderOptions(sampleOptions(state.quiz.current));
}

function renderOptions(options) {
  const fragment = document.createDocumentFragment();
  for (const option of options) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = option.term;
    button.addEventListener("click", () => answerQuiz(option, button));
    fragment.append(button);
  }
  els.options.replaceChildren(fragment);
}

function answerQuiz(option, button) {
  if (state.quiz.answered || !state.quiz.current) {
    return;
  }
  state.quiz.answered = true;
  state.quiz.total += 1;
  const correct = option.id === state.quiz.current.id;
  if (correct) {
    state.quiz.correct += 1;
  }
  const record = updateProficiency(state.quiz.current, correct, option);

  for (const child of els.options.children) {
    child.disabled = true;
    if (child.textContent === state.quiz.current.term) {
      child.classList.add("correct");
    }
  }
  if (!correct) {
    button.classList.add("wrong");
  }

  els.quizScore.textContent = `${state.quiz.correct} / ${state.quiz.total}`;
  els.testFeedback.hidden = false;
  els.testFeedback.innerHTML = `
    <strong>${correct ? "Correct" : "Wrong"}</strong>
    <span>Answer: ${state.quiz.current.term}</span>
    ${correct ? "" : `<span>Your answer: ${option.term}</span>`}
    <span>Proficiency: ${proficiencyBadge(record)}</span>
  `;
}

function renderMistakes() {
  const missed = state.terms
    .map((term) => ({ term, record: recordFor(term) }))
    .filter((item) => item.record.mistakes > 0)
    .sort((a, b) => {
      const byLevel = a.record.level - b.record.level;
      if (byLevel !== 0) return byLevel;
      return String(b.record.lastAt || "").localeCompare(String(a.record.lastAt || ""));
    });

  els.mistakeSummary.textContent = missed.length
    ? `${missed.length} terms have at least one mistake.`
    : "No mistakes yet. Take a test to start building this log.";

  if (!missed.length) {
    els.mistakeList.innerHTML = `
      <div class="empty-state">
        <strong>No mistakes yet</strong>
        <span>Wrong answers will appear here with their proficiency level.</span>
      </div>
    `;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const { term, record } of missed) {
    const row = document.createElement("article");
    row.className = "mistake-item";
    row.innerHTML = `
      ${thumbnail(term)}
      <div>
        <strong>${term.term}</strong>
        <span>${translateRegion(term.region)} · ${translateCategory(term.category)}</span>
        ${record.lastWrong ? `<span>Last wrong answer: ${record.lastWrong}</span>` : ""}
      </div>
      <div class="mistake-stats">
        ${proficiencyBadge(record)}
        <span>${record.mistakes} mistakes</span>
        <span>${record.attempts} attempts</span>
      </div>
    `;
    fragment.append(row);
  }
  els.mistakeList.replaceChildren(fragment);
}

function clearMistakeLog() {
  for (const [id, record] of Object.entries(state.proficiency)) {
    if (record && typeof record === "object") {
      state.proficiency[id] = {
        ...record,
        mistakes: 0,
        lastWrong: null,
      };
    }
  }
  saveProficiency();
  renderMistakes();
}

function renderAll() {
  renderStats();
  renderList();
  renderStudy();
}

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });
  els.searchInput.addEventListener("input", applyFilters);
  els.regionSelect.addEventListener("change", applyFilters);
  els.imageOnlyToggle.addEventListener("change", applyFilters);
  els.shuffleButton.addEventListener("click", shuffleTerms);
  els.prevButton.addEventListener("click", () => move(-1));
  els.nextButton.addEventListener("click", () => move(1));
  els.nextQuizButton.addEventListener("click", nextQuizQuestion);
  els.clearMistakesButton.addEventListener("click", clearMistakeLog);
  window.addEventListener("keydown", (event) => {
    if (event.target.matches("input, select, button")) {
      return;
    }
    if (state.view !== "wordBank") {
      return;
    }
    if (event.key === "ArrowRight") move(1);
    if (event.key === "ArrowLeft") move(-1);
  });
}

async function init() {
  bindEvents();
  try {
    const response = await fetch("data/wordbank.json");
    state.terms = await response.json();
    state.filtered = state.terms.slice();
    renderRegions();
    applyFilters();
    setView("home");
  } catch (error) {
    els.coverageText.textContent = "Word bank data not found";
    els.homeView.innerHTML = `<div class="empty-state"><strong>wordbank.json not found</strong></div>`;
  }
}

init();
