(() => {
  "use strict";

  const state = {
    appVersion: "2.1.0",
    formulas: [],
    sources: [],
    subjectOrder: [],
    chapterOrder: {},
    subject: "全部",
    chapter: "全部",
    mode: "all",
    query: "",
    favorites: new Set(),
    recent: [],
    selectedId: null,
    visible: [],
    theme: "light",
    pinned: false,
    quickMode: false,
    sidebarCollapsed: false,
    activeTab: "overview",
    hotkeys: {
      configured: "Ctrl+Shift+Space",
      active: null,
      registered: false,
      usingFallback: false,
    },
    lastFocused: null,
  };

  const SYNONYM_RULES = [
    { keys: ["矩阵求逆", "求逆矩阵", "求逆"], terms: ["逆矩阵", "伴随矩阵", "初等变换", "分块矩阵求逆", "矩阵方程"], insight: "识别为矩阵求逆问题；同时检索逆矩阵、伴随矩阵、初等变换与分块求逆。" },
    { keys: ["不会做极限", "极限方法", "求极限"], terms: ["极限", "等价无穷小", "洛必达", "泰勒", "夹逼"], insight: "识别为极限方法选择；优先比较等价无穷小、泰勒、洛必达与夹逼。" },
    { keys: ["相消", "低阶项抵消"], terms: ["高阶差式", "泰勒", "麦克劳林", "主部"], insight: "识别到低阶项相消；一阶等价可能失效，应查看高阶主部或泰勒展开。" },
    { keys: ["方差未知", "总体方差未知"], terms: ["t分布", "样本方差", "置信区间"], insight: "识别为方差未知的正态总体问题；重点查看 t 分布和样本方差。" },
    { keys: ["证明不等式", "不等式证明"], terms: ["中值定理", "单调性", "泰勒", "积分估计"], insight: "识别为不等式证明；可从中值定理、单调性、泰勒余项或积分估计中选工具。" },
    { keys: ["根的个数", "零点个数", "方程根"], terms: ["零点定理", "罗尔定理", "单调性", "根的唯一性"], insight: "识别为方程根问题；先证存在，再用单调性或罗尔定理控制个数。" },
    { keys: ["求面积", "面积怎么求"], terms: ["定积分", "二重积分", "面积"], insight: "识别为面积问题；根据区域表示选择定积分或二重积分。" },
    { keys: ["求体积", "体积怎么求"], terms: ["定积分", "三重积分", "二重积分", "体积"], insight: "识别为体积问题；根据旋转体或空间区域选择积分模型。" },
    { keys: ["正态近似", "近似正态"], terms: ["中心极限定理", "棣莫弗", "正态分布"], insight: "识别为正态近似；检查独立同分布、样本量与连续性修正。" },
    { keys: ["路径无关", "与路径无关"], terms: ["格林公式", "全微分", "保守场", "曲线积分"], insight: "识别为路径无关问题；检查区域单连通和偏导交叉条件。" },
    { keys: ["换序积分", "积分换序"], terms: ["二重积分换序", "积分区域", "累次积分"], insight: "识别为积分换序；先画区域，再重写上下限。" },
  ];

  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];

  const el = {
    app: $("#app"),
    loading: $("#loading-screen"),
    subjectNav: $("#subject-nav"),
    chapterNav: $("#chapter-nav"),
    resultList: $("#result-list"),
    noResults: $("#no-results"),
    search: $("#search-input"),
    searchWrap: $(".search-wrap"),
    viewTitle: $("#view-title"),
    resultSummary: $("#result-summary"),
    searchTime: $("#search-time"),
    activeFilters: $("#active-filters"),
    searchInsight: $("#search-insight"),
    searchInsightText: $("#search-insight-text"),
    detailEmpty: $("#detail-empty"),
    detailContent: $("#detail-content"),
    detailTitle: $("#detail-title"),
    detailBreadcrumb: $("#detail-breadcrumb"),
    detailWhen: $("#detail-when"),
    formulaGroups: $("#formula-groups"),
    conditions: $("#condition-list"),
    pitfalls: $("#pitfall-list"),
    conditionPreview: $("#condition-preview"),
    pitfallPreview: $("#pitfall-preview"),
    keywords: $("#keyword-list"),
    tier: $("#tier-badge"),
    favoriteBtn: $("#favorite-btn"),
    decisionSteps: $("#decision-steps"),
    usageSteps: $("#usage-steps"),
    overviewRelated: $("#overview-related"),
    relatedList: $("#related-list"),
    modalBackdrop: $("#modal-backdrop"),
    modalTitle: $("#modal-title"),
    modalEyebrow: $("#modal-eyebrow"),
    modalBody: $("#modal-body"),
    toast: $("#toast"),
  };

  const normalize = value => String(value || "")
    .toLowerCase()
    .replace(/[\s·—\-_/\\()[\]{}，。；：、"'`~!@#$%^&*+=<>?！￥…（）【】《》]/g, "");

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }

  function regexEscape(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function highlightText(value) {
    let output = escapeHtml(value);
    const words = state.query.trim().split(/\s+/).filter(Boolean).sort((a, b) => b.length - a.length);
    for (const word of words) {
      if (word.length < 2) continue;
      output = output.replace(new RegExp(regexEscape(escapeHtml(word)), "gi"), match => `<mark>${match}</mark>`);
    }
    return output;
  }

  function searchable(card) {
    return normalize([
      card.title, card.subject, card.chapter, card.when, card.latex, card.copyText,
      ...(card.aliases || []), ...(card.problemTypes || []), ...(card.questionSignals || []),
      ...(card.conditions || []), ...(card.pitfalls || []), ...(card.keywords || []),
    ].join(" "));
  }

  function latexPreview(value) {
    return String(value || "")
      .replace(/\\begin\{[^}]+}|\\end\{[^}]+}/g, " ")
      .replace(/\\(qquad|quad)/g, " · ")
      .replace(/\\\\\s*/g, " · ")
      .replace(/\\(text|mathrm)\{([^}]*)}/g, "$2")
      .replace(/\\(frac)\{([^}]*)}\{([^}]*)}/g, "$2/$3")
      .replace(/\\sim/g, " ∼ ")
      .replace(/\\to/g, " → ")
      .replace(/\\infty/g, "∞")
      .replace(/\\leq?/g, "≤")
      .replace(/\\geq?/g, "≥")
      .replace(/\\neq?/g, "≠")
      .replace(/\\(sin|cos|tan|arcsin|arctan|ln|log|lim|sum|int|sqrt)/g, "$1")
      .replace(/[{}&]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function queryProfile(query) {
    const full = normalize(query);
    const words = query.trim().split(/\s+/).map(normalize).filter(Boolean);
    const rules = SYNONYM_RULES.filter(rule =>
      rule.keys.some(key => full.includes(normalize(key)) || normalize(key).includes(full) && full.length >= 3)
    );
    const chars = [...full];
    const bigrams = [];
    if (words.length <= 1 && chars.length >= 4) {
      for (let i = 0; i < chars.length - 1; i += 1) bigrams.push(chars.slice(i, i + 2).join(""));
    }
    return {
      full,
      words,
      bigrams: [...new Set(bigrams)],
      expansions: [...new Set(rules.flatMap(rule => rule.terms.map(normalize)))],
      insight: rules[0]?.insight || "",
    };
  }

  function scoreCard(card, profile) {
    if (!profile.full) return 0;
    const title = normalize(card.title);
    const keywords = normalize((card.keywords || []).join(" "));
    const blob = card._search;
    let score = 0;
    let matched = 0;

    if (title === profile.full) { score += 260; matched += 3; }
    else if (title.startsWith(profile.full)) { score += 130; matched += 2; }
    else if (title.includes(profile.full)) { score += 95; matched += 2; }
    else if (blob.includes(profile.full)) { score += 58; matched += 1; }

    let wordMatches = 0;
    for (const word of profile.words) {
      if (!word) continue;
      if (title.includes(word)) { score += 36; wordMatches += 1; }
      else if (keywords.includes(word)) { score += 24; wordMatches += 1; }
      else if (blob.includes(word)) { score += 13; wordMatches += 1; }
    }
    matched += wordMatches;

    let expansionMatches = 0;
    for (const term of profile.expansions) {
      if (title.includes(term)) { score += 42; expansionMatches += 1; }
      else if (keywords.includes(term)) { score += 26; expansionMatches += 1; }
      else if (blob.includes(term)) { score += 15; expansionMatches += 1; }
    }
    matched += expansionMatches;

    let bigramMatches = 0;
    for (const term of profile.bigrams) {
      if (title.includes(term)) { score += 8; bigramMatches += 1; }
      else if (blob.includes(term)) { score += 3; bigramMatches += 1; }
    }

    if (!matched && bigramMatches < 2) return -1;
    if (profile.words.length > 1 && !expansionMatches &&
        wordMatches < profile.words.length) return -1;
    if (/[a-z0-9]/.test(profile.full) && !matched &&
        bigramMatches < Math.max(2, Math.ceil(profile.bigrams.length * .75))) return -1;
    if (profile.full.includes("矩阵求逆") && title.includes("逆矩阵运算")) score += 90;
    if (card.tier === "核心") score += 5;
    else if (card.tier === "重要") score += 2;
    return score;
  }

  function currentCards() {
    let cards = state.formulas;
    if (state.mode === "favorites") cards = cards.filter(card => state.favorites.has(card.id));
    if (state.mode === "recent") {
      const index = new Map(state.formulas.map(card => [card.id, card]));
      cards = state.recent.map(id => index.get(id)).filter(Boolean);
    }
    if (state.subject !== "全部") cards = cards.filter(card => card.subject === state.subject);
    if (state.chapter !== "全部") cards = cards.filter(card => card.chapter === state.chapter);

    const profile = queryProfile(state.query);
    if (profile.full) {
      cards = cards.map(card => ({ card, score: scoreCard(card, profile) }))
        .filter(item => item.score >= 0)
        .sort((a, b) => b.score - a.score || a.card._index - b.card._index)
        .map(item => item.card);
    }
    return cards;
  }

  function subjectClass(subject) {
    if (subject === "线性代数") return "linear";
    if (subject === "概率论与数理统计") return "probability";
    return "calculus";
  }

  function renderSubjects() {
    const counts = new Map();
    state.formulas.forEach(card => counts.set(card.subject, (counts.get(card.subject) || 0) + 1));
    const items = ["全部", ...state.subjectOrder];
    el.subjectNav.innerHTML = items.map(subject => {
      const count = subject === "全部" ? state.formulas.length : counts.get(subject) || 0;
      const icon = subject === "全部"
        ? '<span class="nav-icon">∑</span>'
        : `<span class="subject-dot ${subjectClass(subject)}"></span>`;
      return `<button class="subject-item ${state.subject === subject ? "is-active" : ""}" data-subject="${escapeHtml(subject)}">
        ${icon}<span class="nav-text">${escapeHtml(subject)}</span><span class="nav-count">${count}</span>
      </button>`;
    }).join("");
    $$(".subject-item").forEach(button => button.addEventListener("click", () => {
      state.subject = button.dataset.subject;
      state.chapter = "全部";
      renderNavigation();
      applyView();
    }));
  }

  function renderChapters() {
    const subjects = state.subject === "全部" ? state.subjectOrder : [state.subject];
    const chapters = [];
    subjects.forEach(subject => (state.chapterOrder[subject] || []).forEach(chapter => {
      if (!chapters.includes(chapter)) chapters.push(chapter);
    }));
    el.chapterNav.innerHTML =
      `<button class="chapter-item ${state.chapter === "全部" ? "is-active" : ""}" data-chapter="全部">全部章节</button>` +
      chapters.map(chapter => {
        const count = state.formulas.filter(card =>
          card.chapter === chapter && (state.subject === "全部" || card.subject === state.subject)
        ).length;
        return `<button class="chapter-item ${state.chapter === chapter ? "is-active" : ""}" data-chapter="${escapeHtml(chapter)}">
          ${escapeHtml(chapter)} <span class="nav-count">· ${count}</span>
        </button>`;
      }).join("");
    $$(".chapter-item").forEach(button => button.addEventListener("click", () => {
      state.chapter = button.dataset.chapter;
      renderNavigation();
      applyView();
    }));
  }

  function renderNavigation() {
    renderSubjects();
    renderChapters();
    $$(".nav-item").forEach(button =>
      button.classList.toggle("is-active", button.dataset.mode === state.mode));
  }

  function renderHeader(cards, elapsed) {
    const modeNames = { all: "搜索结果", favorites: "收藏与错题", recent: "最近查看" };
    let title = modeNames[state.mode];
    if (!state.query && state.chapter !== "全部") title = state.chapter;
    else if (!state.query && state.subject !== "全部") title = state.subject;
    else if (!state.query && state.mode === "all") title = "全部公式";
    el.viewTitle.textContent = title;

    const subjectSuffix = state.subject === "全部" ? "数学一全科" : state.subject;
    el.resultSummary.textContent = state.query
      ? `找到 ${cards.length} 条匹配 · ${subjectSuffix}`
      : `${cards.length} 个主题 · 公式、使用判断与易错边界`;
    el.searchTime.textContent = state.query ? `用时 ${Math.max(1, Math.round(elapsed))} ms` : "";

    const filters = [];
    if (state.subject !== "全部") filters.push(["subject", state.subject]);
    if (state.chapter !== "全部") filters.push(["chapter", state.chapter]);
    if (state.query) filters.push(["query", `“${state.query}”`]);
    el.activeFilters.innerHTML = filters.map(([type, label]) =>
      `<button class="filter-chip" data-filter="${type}">${escapeHtml(label)} ×</button>`).join("");
    el.activeFilters.classList.toggle("is-hidden", !filters.length);
    $$(".filter-chip").forEach(button => button.addEventListener("click", () => {
      if (button.dataset.filter === "subject") { state.subject = "全部"; state.chapter = "全部"; }
      if (button.dataset.filter === "chapter") state.chapter = "全部";
      if (button.dataset.filter === "query") {
        state.query = "";
        el.search.value = "";
        updateSearchUi();
      }
      renderNavigation();
      applyView();
    }));

    const profile = queryProfile(state.query);
    let insight = profile.insight;
    if (!insight && state.query && cards.length) {
      insight = `已同时检索标题、公式表达式、题型、使用场景、条件和易错点；结果按相关度排序。`;
    }
    el.searchInsightText.textContent = insight;
    el.searchInsight.classList.toggle("is-hidden", !insight);

    $("#all-count").textContent = state.formulas.length;
    $("#fav-count").textContent = state.favorites.size;
    $("#recent-count").textContent = state.recent.length;
  }

  function renderSuggestions() {
    const profile = queryProfile(state.query);
    const values = profile.expansions.slice(0, 5);
    if (!values.length) values.push("极限方法", "矩阵求逆", "方差未知", "二重积分换序");
    $("#no-results-copy").textContent = state.query
      ? `没有直接找到“${state.query}”。可以尝试下面的相关表达，或减少筛选条件。`
      : "当前范围内没有内容，可以切换科目或清除筛选。";
    $("#suggestion-list").innerHTML = values.map(value =>
      `<button class="suggestion" data-query="${escapeHtml(value)}">${escapeHtml(value)}</button>`).join("");
    $$(".suggestion").forEach(button => button.addEventListener("click", () => {
      el.search.value = button.dataset.query;
      state.query = button.dataset.query;
      updateSearchUi();
      applyView();
    }));
  }

  function renderResults(cards) {
    state.visible = cards;
    el.noResults.classList.toggle("is-hidden", cards.length > 0);
    el.resultList.classList.toggle("is-hidden", cards.length === 0);
    if (!cards.length) {
      el.resultList.innerHTML = "";
      renderSuggestions();
      return;
    }

    el.resultList.innerHTML = cards.map(card => `
      <button class="result-card ${card.id === state.selectedId ? "is-selected" : ""}"
              data-id="${escapeHtml(card.id)}" aria-pressed="${card.id === state.selectedId}">
        <span class="card-top">
          <span class="subject-dot ${subjectClass(card.subject)}"></span>
          <span>${escapeHtml(card.chapter)}</span>
          <span class="card-tier">${escapeHtml(card.tier || card.priority || "常用")}</span>
        </span>
        <span class="card-title">${highlightText(card.title)}</span>
        <span class="card-when">${escapeHtml(card.when)}</span>
        <span class="card-formula">${escapeHtml(latexPreview(card.latex).slice(0, 105))}</span>
        ${state.favorites.has(card.id) ? '<span class="card-star">★</span>' : ""}
      </button>
    `).join("");
    $$(".result-card").forEach(button =>
      button.addEventListener("click", () => selectCard(button.dataset.id)));
  }

  function splitFormulaRows(latex) {
    if (/\\begin\{/.test(latex)) return [latex];
    const rows = latex.split(/\\\\\s+/).map(value => value.trim()).filter(Boolean);
    return rows.length ? rows : [latex];
  }

  function renderFormulaRows(card) {
    const rows = splitFormulaRows(card.latex);
    el.formulaGroups.innerHTML = rows.map((row, index) =>
      `<div class="formula-row"><div class="formula-target" data-row="${index}"></div>
       <button class="row-copy" data-row-copy="${index}" title="复制这一行" aria-label="复制第 ${index + 1} 行">⧉</button></div>`
    ).join("");

    rows.forEach((row, index) => {
      const target = el.formulaGroups.querySelector(`[data-row="${index}"]`);
      try {
        const expression = rows.length === 1 && /\\\\/.test(row)
          ? `\\begin{aligned}${row}\\end{aligned}`
          : row;
        katex.render(expression, target, {
          displayMode: true,
          throwOnError: true,
          strict: false,
          trust: false,
          output: "html",
        });
      } catch (error) {
        target.innerHTML = `<div class="formula-error">公式排版失败：${escapeHtml(error.message)}<br>${escapeHtml(row)}</div>`;
      }
    });
    $$("[data-row-copy]").forEach(button => button.addEventListener("click", () => {
      const row = rows[Number(button.dataset.rowCopy)];
      copyText(row, "这一行 LaTeX 已复制");
    }));
    $("#formula-caption").textContent = `${rows.length} 组公式 · 可逐行复制`;
  }

  function relatedCards(card, limit = 6) {
    const keywords = new Set((card.keywords || []).map(normalize));
    return state.formulas
      .filter(candidate => candidate.id !== card.id)
      .map(candidate => {
        let score = 0;
        if (candidate.subject === card.subject) score += 2;
        if (candidate.chapter === card.chapter) score += 7;
        for (const word of candidate.keywords || []) if (keywords.has(normalize(word))) score += 3;
        return { candidate, score };
      })
      .filter(item => item.score > 2)
      .sort((a, b) => b.score - a.score || a.candidate._index - b.candidate._index)
      .slice(0, limit)
      .map(item => item.candidate);
  }

  function openRelated(card) {
    state.mode = "all";
    state.subject = card.subject;
    state.chapter = "全部";
    state.query = "";
    el.search.value = "";
    updateSearchUi();
    renderNavigation();
    applyView();
    selectCard(card.id);
  }

  function renderRelated(card) {
    const related = relatedCards(card);
    el.overviewRelated.innerHTML = related.slice(0, 4).map(item =>
      `<button class="related-chip" data-related="${escapeHtml(item.id)}">相关：${escapeHtml(item.title)}</button>`
    ).join("");
    el.relatedList.innerHTML = related.map(item => `
      <button class="related-card" data-related="${escapeHtml(item.id)}">
        <h4>${escapeHtml(item.title)}</h4>
        <p>${escapeHtml(item.when)}</p>
      </button>`).join("");
    $$("[data-related]").forEach(button => button.addEventListener("click", () => {
      const target = state.formulas.find(item => item.id === button.dataset.related);
      if (target) openRelated(target);
    }));
  }

  function renderUsage(card) {
    const steps = (card.decisionSteps || []).length ? card.decisionSteps : [
      `识别题型：${card.when}`,
      `检查前提：${(card.conditions || []).join("；")}`,
      `代入后复核：${(card.pitfalls || []).join("；")}`,
    ];
    el.usageSteps.innerHTML = steps.map((step, index) => `
      <div class="usage-step">
        <span class="usage-step-number">${index + 1}</span>
        <div><strong>${["识别题型", "核对条件", "代入并复核"][index] || `步骤 ${index + 1}`}</strong>
        <p>${escapeHtml(step)}</p></div>
      </div>`).join("");
  }

  function renderDetail() {
    const card = state.formulas.find(item => item.id === state.selectedId);
    el.detailEmpty.classList.toggle("is-hidden", !!card);
    el.detailContent.classList.toggle("is-hidden", !card);
    if (!card) return;

    el.detailTitle.textContent = card.title;
    el.detailBreadcrumb.textContent = `${card.subject}  /  ${card.chapter}`;
    el.detailWhen.textContent = card.when;
    el.tier.textContent = `${card.tier || card.priority || "常用"} · ${card.priority || "常用"}`;
    el.favoriteBtn.textContent = state.favorites.has(card.id) ? "★ 已收藏" : "☆ 收藏";
    el.favoriteBtn.classList.toggle("is-active", state.favorites.has(card.id));

    const conditions = card.conditions?.length ? card.conditions : ["按公式标注的定义域和运算存在条件使用。"];
    const pitfalls = card.pitfalls?.length ? card.pitfalls : ["注意变量范围、符号和公式适用前提。"];
    el.conditionPreview.innerHTML = conditions.slice(0, 3).map(item => `<li>${escapeHtml(item)}</li>`).join("");
    el.pitfallPreview.innerHTML = pitfalls.slice(0, 3).map(item => `<li>${escapeHtml(item)}</li>`).join("");
    el.conditions.innerHTML = conditions.map(item => `<li>${escapeHtml(item)}</li>`).join("");
    el.pitfalls.innerHTML = pitfalls.map(item => `<li>${escapeHtml(item)}</li>`).join("");
    el.keywords.innerHTML = (card.keywords || []).map(word =>
      `<button class="keyword" data-word="${escapeHtml(word)}">${escapeHtml(word)}</button>`).join("");
    $$(".keyword").forEach(button => button.addEventListener("click", () => {
      el.search.value = button.dataset.word;
      state.query = button.dataset.word;
      updateSearchUi();
      applyView();
    }));

    const decisionSteps = (card.decisionSteps || []).slice(0, 3);
    el.decisionSteps.innerHTML = decisionSteps.map((step, index) =>
      `<div class="step"><b>${["① 先判型", "② 查前提", "③ 套用后复核"][index] || `步骤 ${index + 1}`}</b>${escapeHtml(step)}</div>`
    ).join("");

    renderFormulaRows(card);
    renderUsage(card);
    renderRelated(card);
    $("#verification-text").textContent =
      `内容版本 ${state.appVersion} · 最近复核 ${card.verifiedAt || "2026-07"} · ${card.scopeVersion || "数学一范围"}`;
    switchTab(state.activeTab);
  }

  function applyView() {
    const started = performance.now();
    const cards = currentCards();
    if (!cards.some(card => card.id === state.selectedId)) state.selectedId = cards[0]?.id || null;
    const elapsed = performance.now() - started;
    renderHeader(cards, elapsed);
    renderResults(cards);
    renderDetail();
  }

  function selectCard(id, updateRecent = true) {
    state.selectedId = id;
    if (updateRecent) {
      state.recent = [id, ...state.recent.filter(value => value !== id)].slice(0, 30);
      window.pywebview?.api?.record_recent(id);
    }
    renderHeader(currentCards(), 0);
    renderResults(currentCards());
    renderDetail();
    $(".result-card.is-selected")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function updateSearchUi() {
    el.searchWrap.classList.toggle("has-value", !!el.search.value);
  }

  async function copyText(text, successMessage = "LaTeX 已复制") {
    const ok = await window.pywebview?.api?.copy_text(String(text));
    showToast(ok ? successMessage : "复制失败");
  }

  async function copyCurrent() {
    const card = state.formulas.find(item => item.id === state.selectedId);
    if (card) await copyText(card.copyText || card.latex, "全部 LaTeX 已复制");
  }

  async function toggleFavorite() {
    if (!state.selectedId) return;
    if (state.favorites.has(state.selectedId)) state.favorites.delete(state.selectedId);
    else state.favorites.add(state.selectedId);
    await window.pywebview?.api?.set_favorite(state.selectedId, state.favorites.has(state.selectedId));
    applyView();
    showToast(state.favorites.has(state.selectedId) ? "已加入收藏" : "已取消收藏");
  }

  async function setTheme(theme) {
    state.theme = theme;
    document.documentElement.dataset.theme = theme;
    await window.pywebview?.api?.save_setting("theme", theme);
  }

  async function setQuickMode(enabled) {
    state.quickMode = !!enabled;
    el.app.classList.toggle("quick-mode", state.quickMode);
    $("#quick-mode-btn").classList.toggle("is-active", state.quickMode);
    $("#quick-mode-btn").setAttribute("aria-pressed", String(state.quickMode));
    await window.pywebview?.api?.save_setting("quickMode", state.quickMode);
    showToast(state.quickMode ? "已开启速查模式" : "已显示完整详情");
  }

  async function setSidebarCollapsed(enabled) {
    state.sidebarCollapsed = !!enabled;
    el.app.classList.toggle("is-sidebar-collapsed", state.sidebarCollapsed);
    await window.pywebview?.api?.save_setting("sidebarCollapsed", state.sidebarCollapsed);
  }

  function setMode(mode) {
    state.mode = mode;
    renderNavigation();
    applyView();
  }

  function resetFilters() {
    state.subject = "全部";
    state.chapter = "全部";
    state.mode = "all";
    state.query = "";
    el.search.value = "";
    updateSearchUi();
    renderNavigation();
    applyView();
    el.search.focus();
  }

  function showToast(message) {
    el.toast.textContent = message;
    el.toast.classList.add("is-visible");
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => el.toast.classList.remove("is-visible"), 1600);
  }

  function openModal() {
    state.lastFocused = document.activeElement;
    el.modalBackdrop.classList.remove("is-hidden");
    $("#modal-close").focus();
  }

  function closeModal() {
    el.modalBackdrop.classList.add("is-hidden");
    state.lastFocused?.focus?.();
  }

  function showSources(currentOnly = false) {
    const card = state.formulas.find(item => item.id === state.selectedId);
    const used = new Set(card?.sourceRefs || []);
    el.modalEyebrow.textContent = currentOnly ? "FORMULA AUDIT" : "CONTENT AUDIT";
    el.modalTitle.textContent = currentOnly && card ? `${card.title} · 来源与核验` : "资料来源与内容校验";
    const sources = currentOnly && used.size
      ? state.sources.filter(source => used.has(source.id))
      : state.sources;
    el.modalBody.innerHTML = `
      <p class="audit-note">${currentOnly && card
        ? `本条最近复核于 ${escapeHtml(card.verifiedAt || "2026-07")}；公式已通过离线排版检查，代表性高风险内容另做符号核验。`
        : `当前收录 ${state.formulas.length} 个主题。全部公式均执行结构和 KaTeX 排版检查，高风险内容执行代表性符号核验。`}</p>
      ${sources.map(source => `<div class="source-card ${used.has(source.id) ? "is-used" : ""}">
        <h3>${escapeHtml(source.name)}${used.has(source.id) ? " · 本条引用" : ""}</h3>
        <p>${escapeHtml(source.note)}</p>
        <button data-url="${escapeHtml(source.url)}">打开来源 ↗</button>
      </div>`).join("")}
      <p style="font-size:10px">说明：本工具用于复习与快速检索，不替代教材证明和报考年度正式考试大纲。发现疑点时应回到定义、教材和大纲核对。</p>`;
    el.modalBody.querySelectorAll("[data-url]").forEach(button =>
      button.addEventListener("click", () => window.pywebview?.api?.open_url(button.dataset.url)));
    openModal();
  }

  function showShortcuts() {
    el.modalEyebrow.textContent = "KEYBOARD";
    el.modalTitle.textContent = "快捷键设置与使用说明";
    const configured = state.hotkeys.configured || "Ctrl+Shift+Space";
    const shortcuts = [
      [displayShortcut(configured), "从任何位置唤出或隐藏窗口（可自定义）"],
      ["Ctrl + Alt + M", "自定义组合键注册失败时的安全备用键"],
      ["Ctrl + K", "聚焦并全选搜索框"],
      ["↑ / ↓", "搜索框或结果区聚焦时移动选择"],
      ["Enter", "打开首条搜索结果"],
      ["Ctrl + D", "收藏或取消收藏当前公式"],
      ["Ctrl + Shift + C", "复制当前公式全部 LaTeX"],
      ["Alt + 1 / 2 / 3", "切换高数、线代、概率"],
      ["Esc", "关闭弹窗、清空搜索或隐藏窗口"],
    ];
    el.modalBody.innerHTML = `
      <section class="hotkey-settings">
        <div class="hotkey-settings-head">
          <div>
            <h3>全局唤出快捷键</h3>
            <p>点击下方按键框，然后直接按下新的组合键。</p>
          </div>
          <span class="hotkey-state ${state.hotkeys.registered ? "is-ok" : "is-error"}">
            ${state.hotkeys.registered
              ? `${escapeHtml(displayShortcut(state.hotkeys.active || configured))} 已生效`
              : "当前未注册"}
          </span>
        </div>
        <button id="hotkey-recorder" class="hotkey-recorder" type="button"
                data-shortcut="${escapeHtml(configured)}">
          <span class="recorder-label">当前组合键</span>
          <strong>${escapeHtml(displayShortcut(configured))}</strong>
          <span class="recorder-tip">点击后录入</span>
        </button>
        <p class="hotkey-rule">至少包含 Ctrl、Alt 或 Win；支持字母、数字、Space、F1–F12。</p>
        <div class="hotkey-actions">
          <button id="hotkey-save" class="primary-button" type="button">应用新快捷键</button>
          <button id="hotkey-reset" class="secondary-button" type="button">恢复默认</button>
          <span id="hotkey-editor-status" class="hotkey-editor-status" aria-live="polite"></span>
        </div>
      </section>
      <div class="shortcut-grid">${shortcuts.map(([key, desc]) =>
        `<div><kbd>${escapeHtml(key)}</kbd></div><div>${desc}</div>`).join("")}</div>`;
    bindHotkeyEditor();
    openModal();
  }

  function displayShortcut(shortcut) {
    return String(shortcut || "").split("+").join(" + ");
  }

  function shortcutFromEvent(event) {
    let key = "";
    if (event.code === "Space") key = "Space";
    else if (/^Key[A-Z]$/.test(event.code)) key = event.code.slice(3);
    else if (/^Digit[0-9]$/.test(event.code)) key = event.code.slice(5);
    else if (/^F(?:[1-9]|1[0-2])$/.test(event.key)) key = event.key.toUpperCase();
    if (!key) return null;
    const parts = [];
    if (event.ctrlKey) parts.push("Ctrl");
    if (event.altKey) parts.push("Alt");
    if (event.shiftKey) parts.push("Shift");
    if (event.metaKey) parts.push("Win");
    if (!event.ctrlKey && !event.altKey && !event.metaKey) return "modifier-required";
    parts.push(key);
    return parts.join("+");
  }

  function bindHotkeyEditor() {
    const recorder = $("#hotkey-recorder");
    const saveButton = $("#hotkey-save");
    const resetButton = $("#hotkey-reset");
    const status = $("#hotkey-editor-status");
    if (!recorder || !saveButton || !resetButton || !status) return;

    const showRecorded = shortcut => {
      recorder.dataset.shortcut = shortcut;
      recorder.querySelector(".recorder-label").textContent = "准备应用";
      recorder.querySelector("strong").textContent = displayShortcut(shortcut);
      recorder.querySelector(".recorder-tip").textContent = "可继续修改";
      status.textContent = "点击“应用新快捷键”后立即生效";
      status.className = "hotkey-editor-status";
    };

    const applyShortcut = async shortcut => {
      saveButton.disabled = true;
      resetButton.disabled = true;
      status.textContent = "正在检查组合键是否可用…";
      status.className = "hotkey-editor-status";
      try {
        const result = await window.pywebview?.api?.set_hotkey(shortcut);
        if (!result) throw new Error("快捷键服务无响应");
        state.hotkeys = { ...state.hotkeys, ...result };
        status.textContent = result.message || (result.ok ? "快捷键已生效" : "设置失败");
        status.className = `hotkey-editor-status ${result.ok ? "is-ok" : "is-error"}`;
        if (result.ok) {
          const current = result.configured || shortcut;
          recorder.dataset.shortcut = current;
          recorder.querySelector(".recorder-label").textContent = "当前组合键";
          recorder.querySelector("strong").textContent = displayShortcut(current);
          recorder.querySelector(".recorder-tip").textContent = "点击后录入";
          renderRuntimeStatus(false);
        }
      } catch (error) {
        status.textContent = error.message || "设置失败，请重试";
        status.className = "hotkey-editor-status is-error";
      } finally {
        saveButton.disabled = false;
        resetButton.disabled = false;
      }
    };

    recorder.addEventListener("click", () => {
      recorder.classList.add("is-recording");
      recorder.querySelector(".recorder-label").textContent = "正在录入";
      recorder.querySelector("strong").textContent = "请按组合键…";
      recorder.querySelector(".recorder-tip").textContent = "Esc 取消";
      status.textContent = "";
    });
    recorder.addEventListener("blur", () => recorder.classList.remove("is-recording"));
    recorder.addEventListener("keydown", event => {
      event.preventDefault();
      event.stopPropagation();
      if (event.key === "Escape") {
        const current = state.hotkeys.configured || "Ctrl+Shift+Space";
        recorder.dataset.shortcut = current;
        recorder.querySelector(".recorder-label").textContent = "当前组合键";
        recorder.querySelector("strong").textContent = displayShortcut(current);
        recorder.querySelector(".recorder-tip").textContent = "点击后录入";
        recorder.classList.remove("is-recording");
        status.textContent = "已取消修改";
        return;
      }
      if (["Control", "Alt", "Shift", "Meta"].includes(event.key)) {
        recorder.querySelector("strong").textContent = "请再按一个普通按键…";
        return;
      }
      const shortcut = shortcutFromEvent(event);
      if (shortcut === "modifier-required") {
        status.textContent = "至少需要 Ctrl、Alt 或 Win 中的一个";
        status.className = "hotkey-editor-status is-error";
        return;
      }
      if (!shortcut) {
        status.textContent = "该按键暂不支持，请使用字母、数字、Space 或 F1–F12";
        status.className = "hotkey-editor-status is-error";
        return;
      }
      recorder.classList.remove("is-recording");
      showRecorded(shortcut);
    });
    saveButton.addEventListener("click", () => applyShortcut(recorder.dataset.shortcut));
    resetButton.addEventListener("click", () => {
      showRecorded("Ctrl+Shift+Space");
      applyShortcut("Ctrl+Shift+Space");
    });
  }

  function switchTab(tab) {
    state.activeTab = ["overview", "conditions", "example", "related"].includes(tab) ? tab : "overview";
    $$(".detail-tab").forEach(button =>
      button.classList.toggle("is-active", button.dataset.tab === state.activeTab));
    $$(".tab-panel").forEach(panel =>
      panel.classList.toggle("is-active", panel.id === `tab-${state.activeTab}`));
    $(".detail-scroll")?.scrollTo({ top: 0, behavior: "auto" });
  }

  function moveSelection(delta) {
    if (!state.visible.length) return;
    let index = state.visible.findIndex(card => card.id === state.selectedId);
    index = index < 0
      ? (delta > 0 ? 0 : state.visible.length - 1)
      : Math.max(0, Math.min(state.visible.length - 1, index + delta));
    selectCard(state.visible[index].id);
  }

  function trapModalFocus(event) {
    if (event.key !== "Tab" || el.modalBackdrop.classList.contains("is-hidden")) return;
    const focusable = [...$("#modal").querySelectorAll("button, [href], input, [tabindex]:not([tabindex='-1'])")]
      .filter(item => !item.disabled);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  function bindEvents() {
    el.search.addEventListener("input", () => {
      state.query = el.search.value.trim();
      updateSearchUi();
      applyView();
    });
    $("#clear-search").addEventListener("click", () => {
      el.search.value = "";
      state.query = "";
      updateSearchUi();
      applyView();
      el.search.focus();
    });
    $$(".nav-item").forEach(button => button.addEventListener("click", () => setMode(button.dataset.mode)));
    $("#reset-filter").addEventListener("click", resetFilters);
    $("#favorite-btn").addEventListener("click", toggleFavorite);
    $("#copy-btn").addEventListener("click", copyCurrent);
    $("#copy-group-btn").addEventListener("click", copyCurrent);
    $("#sources-btn").addEventListener("click", () => showSources(false));
    $("#detail-source-btn").addEventListener("click", () => showSources(true));
    $("#help-btn").addEventListener("click", showShortcuts);
    $("#modal-close").addEventListener("click", closeModal);
    el.modalBackdrop.addEventListener("click", event => {
      if (event.target === el.modalBackdrop) closeModal();
    });
    $("#hide-btn").addEventListener("click", () => window.pywebview?.api?.hide_app());
    $("#theme-btn").addEventListener("click", () => setTheme(state.theme === "dark" ? "light" : "dark"));
    $("#quick-mode-btn").addEventListener("click", () => setQuickMode(!state.quickMode));
    $("#sidebar-toggle").addEventListener("click", () => setSidebarCollapsed(!state.sidebarCollapsed));
    $("#pin-btn").addEventListener("click", async () => {
      state.pinned = await window.pywebview?.api?.toggle_pin();
      $("#pin-btn").classList.toggle("is-active", state.pinned);
      showToast(state.pinned ? "窗口已置顶" : "已取消置顶");
    });
    $$(".detail-tab").forEach(button =>
      button.addEventListener("click", () => switchTab(button.dataset.tab)));

    document.addEventListener("keydown", event => {
      trapModalFocus(event);
      if (event.ctrlKey && event.key.toLowerCase() === "k") {
        event.preventDefault(); el.search.focus(); el.search.select(); return;
      }
      if (event.ctrlKey && event.key.toLowerCase() === "d") {
        event.preventDefault(); toggleFavorite(); return;
      }
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "c") {
        event.preventDefault(); copyCurrent(); return;
      }
      if (event.altKey && ["1", "2", "3"].includes(event.key)) {
        event.preventDefault();
        state.subject = state.subjectOrder[Number(event.key) - 1];
        state.chapter = "全部";
        renderNavigation();
        applyView();
        return;
      }
      const resultNavigation = document.activeElement === el.search ||
        document.activeElement?.closest?.(".result-pane");
      if (resultNavigation && event.key === "ArrowDown") { event.preventDefault(); moveSelection(1); return; }
      if (resultNavigation && event.key === "ArrowUp") { event.preventDefault(); moveSelection(-1); return; }
      if (event.key === "Enter" && document.activeElement === el.search && state.visible[0]) {
        selectCard(state.visible[0].id); return;
      }
      if (event.key === "Escape") {
        if (!el.modalBackdrop.classList.contains("is-hidden")) closeModal();
        else if (state.query) {
          el.search.value = ""; state.query = ""; updateSearchUi(); applyView();
        } else window.pywebview?.api?.hide_app();
      }
    });
  }

  function renderRuntimeStatus(showWarnings = true) {
    $("#app-version").textContent = `v${state.appVersion}`;
    $("#library-status").innerHTML = `<span class="status-dot"></span><span>${state.formulas.length} 条 · v${state.appVersion} · 已校验</span>`;
    const hotkeyHint = $("#hotkey-hint");
    if (state.hotkeys.registered) {
      const active = state.hotkeys.active || state.hotkeys.configured || "Ctrl+Shift+Space";
      hotkeyHint.innerHTML = `${active.split("+").map(part =>
        `<kbd>${escapeHtml(part)}</kbd>`).join("<span>+</span>")}<span>${state.hotkeys.usingFallback ? "备用唤出" : "唤出"}</span>`;
      if (state.hotkeys.usingFallback && showWarnings) {
        showToast(`${displayShortcut(state.hotkeys.configured)} 被占用，已启用 Ctrl + Alt + M`);
      }
    } else {
      hotkeyHint.innerHTML = "<span>全局快捷键均被占用，请通过托盘唤出</span>";
      if (showWarnings) showToast("全局快捷键注册失败，请通过托盘唤出");
    }
  }

  async function bootstrap() {
    try {
      const data = await window.pywebview.api.get_bootstrap();
      state.appVersion = data.appVersion || "2.1.0";
      state.formulas = data.formulas.map((card, index) => ({
        ...card,
        tier: card.tier || (card.priority === "高频" ? "重要" : "扩展"),
        _index: index,
        _search: searchable(card),
      }));
      state.sources = data.sources;
      state.subjectOrder = data.subjectOrder;
      state.chapterOrder = data.chapterOrder;
      state.favorites = new Set(data.settings.favorites || []);
      state.recent = data.settings.recent || [];
      state.theme = data.settings.theme || "light";
      state.pinned = !!data.settings.pinned;
      state.quickMode = !!data.settings.quickMode;
      state.sidebarCollapsed = !!data.settings.sidebarCollapsed;
      state.hotkeys = data.hotkeys || state.hotkeys;

      document.documentElement.dataset.theme = state.theme;
      $("#pin-btn").classList.toggle("is-active", state.pinned);
      el.app.classList.toggle("quick-mode", state.quickMode);
      el.app.classList.toggle("is-sidebar-collapsed", state.sidebarCollapsed);
      $("#quick-mode-btn").classList.toggle("is-active", state.quickMode);
      $("#quick-mode-btn").setAttribute("aria-pressed", String(state.quickMode));

      bindEvents();
      renderNavigation();
      state.selectedId = state.recent.find(id => state.formulas.some(card => card.id === id)) ||
        state.formulas[0]?.id || null;
      applyView();
      renderRuntimeStatus();
      el.app.classList.remove("is-loading");
      setTimeout(() => el.loading.classList.add("is-done"), 150);
    } catch (error) {
      el.loading.querySelector(".loading-name").textContent = "公式库载入失败";
      el.loading.querySelector(".loading-bar").innerHTML = "";
      console.error(error);
    }
  }

  window.onQuickShow = () => setTimeout(() => {
    el.search.focus();
    el.search.select();
  }, 80);
  window.addEventListener("pywebviewready", bootstrap);
})();
