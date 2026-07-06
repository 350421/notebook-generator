const form = document.querySelector("#generate-form");
const contentInput = document.querySelector("#content");
const charCount = document.querySelector("#char-count");
const generateButton = document.querySelector("#generate-button");
const buttonLabel = generateButton.querySelector(".button-label");
const statusBox = document.querySelector("#status");
const resultsSection = document.querySelector("#results");
const resultSummary = document.querySelector("#result-summary");
const blockEditor = document.querySelector("#block-editor");
const previewGallery = document.querySelector("#preview-gallery");
const refreshButton = document.querySelector("#refresh-button");
const downloadSelectedButton = document.querySelector(
  "#download-selected-button",
);
const downloadAllButton = document.querySelector("#download-all-button");
const imageModal = document.querySelector("#image-modal");
const modalImage = document.querySelector("#modal-image");
const modalCaption = document.querySelector("#modal-caption");
const modalClose = document.querySelector("#modal-close");
const templateTextFields = document.querySelector("#template-text-fields");
const resetTemplateTextButton = document.querySelector("#reset-template-text");
const applyTemplateTextButton = document.querySelector("#apply-template-text");
const templateTextHint = document.querySelector("#template-text-hint");
const templateStyleFields = document.querySelector("#template-style-fields");
const templateStyleTemplateSelect = document.querySelector(
  "#template-style-template-select",
);
const applyTemplateStyleButton = document.querySelector("#apply-template-style");
const resetTemplateStyleButton = document.querySelector("#reset-template-style");
const templateStyleHint = document.querySelector("#template-style-hint");
const coverEnabledInput = document.querySelector("#cover-enabled");
const coverSeparatePageInput = document.querySelector("#cover-separate-page");
const coverPreferImageInput = document.querySelector("#cover-prefer-image");
const coverSubtitleInput = document.querySelector("#cover-subtitle");
const inlineFormatToolbar = document.querySelector("#inline-format-toolbar");
const formatBoldButton = document.querySelector("#format-bold");
const formatColorToggle = document.querySelector("#format-color-toggle");
const formatColorPanel = document.querySelector("#format-color-panel");
const formatCustomColor = document.querySelector("#format-custom-color");
const formatFontSize = document.querySelector("#format-font-size");
const imageFileInput = document.querySelector("#image-file-input");
const uploadImageButton = document.querySelector("#upload-image-button");
const undoButton = document.querySelector("#undo-button");
const redoButton = document.querySelector("#redo-button");
const clearDraftButton = document.querySelector("#clear-draft-button");
const pendingImage = document.querySelector("#pending-image");
const pendingImageThumb = document.querySelector("#pending-image-thumb");
const pendingImageName = document.querySelector("#pending-image-name");
const uploadedImageCount = document.querySelector("#uploaded-image-count");
const uploadedImageList = document.querySelector("#uploaded-image-list");
const imagePickerModal = document.querySelector("#image-picker-modal");
const imagePickerClose = document.querySelector("#image-picker-close");
const imagePickerTarget = document.querySelector("#image-picker-target");
const imagePickerList = document.querySelector("#image-picker-list");
const materialPresetList = document.querySelector("#material-preset-list");
const projectNameInput = document.querySelector("#project-name-input");
const saveProjectButton = document.querySelector("#save-project-button");
const exportProjectButton = document.querySelector("#export-project-button");
const importProjectInput = document.querySelector("#import-project-input");
const projectHistoryList = document.querySelector("#project-history-list");
const templateTextDefaults = JSON.parse(
  document.querySelector("#template-text-defaults").textContent,
);
const templateStyleDefaults = JSON.parse(
  document.querySelector("#template-style-defaults").textContent,
);
const DRAFT_STORAGE_KEY = "notebook_generator_draft_v2";
const PROJECT_LIBRARY_STORAGE_KEY = "notebook_generator_project_library_v1";
const STICKER_PRESET_NAMES = {
  sparkle: "星芒",
  heart: "爱心",
  star: "五角星",
  quote: "引号",
  check: "对勾",
  bolt: "闪电",
};

let currentBlocks = [];
let previewDirty = false;
let activeTemplateTextInput = null;
let savedInlineRange = null;
let activeFormattedEditor = null;
let pendingImageFile = null;
let pendingImageObjectUrl = "";
const uploadedImages = [];
let activeImagePageTarget = null;
let draftSaveTimer = null;
let historySaveTimer = null;
let isRestoringSnapshot = false;
let historySnapshots = [];
let historyCursor = -1;
let lastNativeUndoTarget = null;
let currentTemplateStyleDrafts = structuredClone(templateStyleDefaults);
let activeTemplateStyleName = Object.keys(templateStyleDefaults)[0] || "";
let autoPreviewTimer = null;
let autoPreviewInFlight = false;
let autoPreviewQueued = false;

// 预览只在生成或重新生成时写入；打开、关闭和切换模板只读取该对象。
const previewCache = {};
const selectedTemplates = new Set();


function defaultCoverSettings() {
  return {
    enabled: false,
    separate_page: false,
    prefer_cover_image: true,
    subtitle: "",
  };
}

function collectCoverSettings() {
  return {
    enabled: Boolean(coverEnabledInput?.checked),
    separate_page: Boolean(coverSeparatePageInput?.checked),
    prefer_cover_image: Boolean(coverPreferImageInput?.checked),
    subtitle: coverSubtitleInput?.value?.trim?.() || "",
  };
}

function applyCoverSettings(settings) {
  const next = {...defaultCoverSettings(), ...(settings || {})};
  if (coverEnabledInput) {
    coverEnabledInput.checked = Boolean(next.enabled);
  }
  if (coverSeparatePageInput) {
    coverSeparatePageInput.checked = Boolean(next.separate_page);
  }
  if (coverPreferImageInput) {
    coverPreferImageInput.checked = next.prefer_cover_image !== false;
  }
  if (coverSubtitleInput) {
    coverSubtitleInput.value = next.subtitle || "";
  }
}

function normalizeTemplateStyleValue(fieldName, value) {
  if (["background", "background_secondary", "title_color", "body_color", "accent_color"].includes(fieldName)) {
    return String(value || "");
  }
  if (fieldName === "background_type") {
    return String(value || "solid");
  }
  if (fieldName === "line_height") {
    return Number(value || 1.8);
  }
  return Number(value || 0);
}

function collectTemplateStyleOverrides() {
  const overrides = {};
  Object.entries(currentTemplateStyleDrafts).forEach(([templateName, fields]) => {
    const defaults = templateStyleDefaults[templateName] || {};
    Object.entries(fields || {}).forEach(([fieldName, value]) => {
      if (defaults[fieldName] !== value) {
        if (!overrides[templateName]) {
          overrides[templateName] = {};
        }
        overrides[templateName][fieldName] = value;
      }
    });
  });
  return overrides;
}

contentInput.addEventListener("input", () => {
  charCount.textContent = `${contentInput.value.length} 字`;
  lastNativeUndoTarget = contentInput;
  queueDraftSave();
  queueHistorySnapshot();
});

contentInput.addEventListener("focus", () => {
  lastNativeUndoTarget = contentInput;
});

function isNativeUndoEditable(target) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target === contentInput ||
    target.classList.contains("template-text-input") ||
    target.classList.contains("block-content")
  );
}

function rememberNativeUndoTarget(target) {
  if (isNativeUndoEditable(target)) {
    lastNativeUndoTarget = target;
    updateHistoryButtonState();
  }
}

function currentNativeUndoTarget() {
  if (isNativeUndoEditable(document.activeElement)) {
    return document.activeElement;
  }
  if (isNativeUndoEditable(lastNativeUndoTarget) && lastNativeUndoTarget.isConnected) {
    return lastNativeUndoTarget;
  }
  if (
    isNativeUndoEditable(activeTemplateTextInput) &&
    activeTemplateTextInput.isConnected
  ) {
    return activeTemplateTextInput;
  }
  if (
    isNativeUndoEditable(activeFormattedEditor) &&
    activeFormattedEditor.isConnected
  ) {
    return activeFormattedEditor;
  }
  return null;
}

function setInitialLoading(loading) {
  generateButton.disabled = loading;
  buttonLabel.textContent = loading
    ? "正在生成 10 套预览…"
    : "生成预览";
}

function setRefreshLoading(loading) {
  refreshButton.disabled = loading;
  downloadSelectedButton.disabled = loading;
  downloadAllButton.disabled = loading;
  refreshButton.textContent = loading
    ? "正在重新生成 10 套…"
    : "重新生成预览";
}

function escapeInlineText(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function safeInlineStyle(element) {
  const declarations = [];
  const fontWeight = element.style.fontWeight;
  const color = element.style.color;
  const fontSize = element.style.fontSize;

  if (fontWeight === "700" || fontWeight === "bold") {
    declarations.push("font-weight:700");
  }
  if (
    color &&
    (/^#[0-9a-f]{6}$/i.test(color) ||
      /^rgba?\([\d\s,.%]+\)$/i.test(color) ||
      /^(red|blue|green|orange|purple|black|white)$/i.test(color))
  ) {
    declarations.push(`color:${color}`);
  }
  if (/^(16|20|24|28|32|36)px$/.test(fontSize)) {
    declarations.push(`font-size:${fontSize}`);
  }
  return declarations.join(";");
}

function appendSafeEditorNode(source, target) {
  if (source.nodeType === Node.TEXT_NODE) {
    target.append(document.createTextNode(source.textContent));
    return;
  }
  if (source.nodeType !== Node.ELEMENT_NODE) {
    return;
  }

  const tagName = source.tagName.toLowerCase();
  if (tagName === "br") {
    target.append(document.createElement("br"));
    return;
  }
  if (tagName === "span") {
    const span = document.createElement("span");
    const style = safeInlineStyle(source);
    if (style) {
      span.setAttribute("style", style);
    }
    source.childNodes.forEach((child) => appendSafeEditorNode(child, span));
    target.append(span);
    return;
  }
  if (tagName === "strong" || tagName === "b") {
    const strong = document.createElement("strong");
    source.childNodes.forEach((child) => appendSafeEditorNode(child, strong));
    target.append(strong);
    return;
  }

  target.append(document.createTextNode(source.outerHTML));
}

function setEditorMarkup(editor, markup) {
  const template = document.createElement("template");
  template.innerHTML = markup;
  editor.replaceChildren();
  template.content.childNodes.forEach((node) => {
    appendSafeEditorNode(node, editor);
  });
}

function serializeEditorNode(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    return escapeInlineText(node.textContent);
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }

  const tagName = node.tagName.toLowerCase();
  if (tagName === "br") {
    return "\n";
  }

  const children = Array.from(node.childNodes)
    .map((child) => serializeEditorNode(child))
    .join("");

  if (tagName === "span") {
    const style = safeInlineStyle(node);
    return style
      ? `<span style="${style}">${children}</span>`
      : children;
  }
  if (tagName === "strong" || tagName === "b") {
    return `<strong>${children}</strong>`;
  }
  if (tagName === "div" || tagName === "p") {
    return `${children}\n`;
  }
  return children;
}

function serializeEditor(editor) {
  return Array.from(editor.childNodes)
    .map((node) => serializeEditorNode(node))
    .join("")
    .replace(/\n+$/, "");
}

function syncBlocksFromEditor() {
  blockEditor.querySelectorAll(".block-content").forEach((editor) => {
    const index = Number(editor.dataset.index);
    currentBlocks[index].content = serializeEditor(editor);
  });
}

function typeLabel(block, index, firstTitleIndex) {
  const labels = {
    body: "正文",
    list: "列表",
    image: "图片",
    sticker: "素材",
    quote: "引用",
  };
  if (block.type === "title") {
    return index === firstTitleIndex ? "一级标题" : "二级标题";
  }
  return labels[block.type] || "内容";
}

function normalizedBlockAlign(block) {
  return block.align === "center" ? "center" : "left";
}

function alignmentLabel(align) {
  return align === "center" ? "居中" : "居左";
}

function normalizedStickerType(block) {
  return block.sticker_type || block.content || "sparkle";
}

function normalizedStickerColor(block) {
  return /^#[0-9a-f]{6}$/i.test(block.sticker_color || "")
    ? block.sticker_color
    : "#D9363E";
}

function normalizedStickerSize(block) {
  const size = Number(block.sticker_size) || 88;
  return Math.max(32, Math.min(240, size));
}

function stickerDisplayName(block) {
  return STICKER_PRESET_NAMES[normalizedStickerType(block)] || "素材";
}

function renderStickerSvgMarkup(stickerType, stickerColor, stickerSize = 88) {
  const fill = /^#[0-9a-f]{6}$/i.test(stickerColor || "")
    ? stickerColor
    : "#D9363E";
  const size = Math.max(32, Math.min(240, Number(stickerSize) || 88));
  const paths = {
    sparkle: '<path d="M46 6l8 20 20 8-20 8-8 20-8-20-20-8 20-8z"/>',
    heart: '<path d="M46 74S12 54 12 31c0-9 7-17 17-17 7 0 13 4 17 10 4-6 10-10 17-10 10 0 17 8 17 17 0 23-34 43-34 43z"/>',
    star: '<path d="M46 10l10 20 22 3-16 15 4 22-20-10-20 10 4-22-16-15 22-3z"/>',
    quote: '<path d="M22 56c0-13 8-23 20-30l4 7c-7 4-10 8-11 14h13v23H22V56zm34 0c0-13 8-23 20-30l4 7c-7 4-10 8-11 14h13v23H56V56z"/>',
    check: '<path d="M34 61L18 45l7-7 9 9 25-25 7 7-32 32z"/>',
    bolt: '<path d="M52 8L18 48h18l-8 32 34-40H44z"/>',
  };
  return `
    <svg viewBox="0 0 92 92" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" width="${size}" height="${size}">
      <g fill="${fill}">${paths[stickerType] || paths.sparkle}</g>
    </svg>
  `;
}

function serializeDraftState() {
  return {
    content: contentInput.value,
    blocks: currentBlocks.map((block) => ({
      type: block.type,
      content: block.content,
      align: normalizedBlockAlign(block),
      ...(block.type === "image" ? { url: block.content, width: "100%" } : {}),
      ...(block.type === "sticker"
        ? {
            sticker_type: normalizedStickerType(block),
            sticker_color: normalizedStickerColor(block),
            sticker_size: normalizedStickerSize(block),
          }
        : {}),
    })),
    templateOverrides: collectTemplateOverrides(),
    templateStyleOverrides: collectTemplateStyleOverrides(),
    coverSettings: collectCoverSettings(),
    uploadedImages: uploadedImages.map((image) => ({
      filename: image.filename,
      originalName: image.originalName,
      url: image.url,
      enabled: image.enabled !== false,
    })),
    projectName: projectNameInput?.value?.trim?.() || "",
    updatedAt: Date.now(),
  };
}

function saveDraftToLocal() {
  try {
    localStorage.setItem(
      DRAFT_STORAGE_KEY,
      JSON.stringify(serializeDraftState()),
    );
  } catch (_error) {
    // 本地存储失败时不打断编辑。
  }
}

function queueDraftSave() {
  window.clearTimeout(draftSaveTimer);
  draftSaveTimer = window.setTimeout(saveDraftToLocal, 400);
}

function hasPreviewToSync() {
  return Object.keys(previewCache).length > 0 && currentBlocks.length > 0;
}

function scheduleAutoPreviewRefresh() {
  if (!hasPreviewToSync()) {
    return;
  }
  window.clearTimeout(autoPreviewTimer);
  autoPreviewTimer = window.setTimeout(async () => {
    if (autoPreviewInFlight) {
      autoPreviewQueued = true;
      return;
    }
    autoPreviewInFlight = true;
    const refreshed = await regenerateEditedPreview({
      successMessage: "预览已自动同步。",
      loadingMessage: "正在自动同步预览…",
      silent: true,
    });
    autoPreviewInFlight = false;
    if (autoPreviewQueued) {
      autoPreviewQueued = false;
      scheduleAutoPreviewRefresh();
    } else if (refreshed) {
      statusBox.textContent = "预览已自动同步。";
      statusBox.className = "status";
    }
  }, 650);
}

function updateHistoryButtonState() {
  if (!undoButton) {
    return;
  }
  undoButton.disabled =
    historyCursor <= 0 && currentNativeUndoTarget() === null;
  if (redoButton) {
    redoButton.disabled =
      historyCursor >= historySnapshots.length - 1 &&
      currentNativeUndoTarget() === null;
  }
}

function attemptNativeHistoryCommand(command) {
  const target = currentNativeUndoTarget();
  if (!target || typeof document.execCommand !== "function") {
    return false;
  }

  const beforeValue =
    target === contentInput || target.classList.contains("template-text-input")
      ? target.value
      : serializeEditor(target);

  target.focus({ preventScroll: true });
  const commandApplied = document.execCommand(command);

  const afterValue =
    target === contentInput || target.classList.contains("template-text-input")
      ? target.value
      : serializeEditor(target);

  const changed = beforeValue !== afterValue;
  if (changed) {
    rememberNativeUndoTarget(target);
    updateHistoryButtonState();
  }
  return commandApplied || changed;
}

function queueHistorySnapshot() {
  if (isRestoringSnapshot) {
    return;
  }
  window.clearTimeout(historySaveTimer);
  historySaveTimer = window.setTimeout(() => {
    pushHistorySnapshot();
  }, 250);
}

function pushHistorySnapshot() {
  if (isRestoringSnapshot) {
    return;
  }
  const snapshot = JSON.stringify(serializeDraftState());
  if (historyCursor >= 0 && historySnapshots[historyCursor] === snapshot) {
    updateHistoryButtonState();
    return;
  }
  historySnapshots = historySnapshots.slice(0, historyCursor + 1);
  historySnapshots.push(snapshot);
  if (historySnapshots.length > 60) {
    historySnapshots.shift();
  }
  historyCursor = historySnapshots.length - 1;
  updateHistoryButtonState();
}

function markPreviewStale() {
  previewDirty = true;
  updateSelectionUI();
  statusBox.textContent =
    hasPreviewToSync()
      ? "内容已调整，正在自动同步预览…"
      : "内容已调整。请先点击「生成预览」，之后的修改会自动同步。";
  statusBox.className = "status";
  queueDraftSave();
  scheduleAutoPreviewRefresh();
}

function templateDisplayName(templateName) {
  const match = templateName.match(/^template_(\d+)_(.*)$/);
  if (!match) {
    return templateName;
  }
  return `第 ${Number(match[1])} 套 - ${match[2]}`;
}

function markTemplateTextChanged() {
  if (currentBlocks.length > 0) {
    markPreviewStale();
  }
  queueDraftSave();
  queueHistorySnapshot();
}

function markTemplateStyleChanged(message = "模板参数已更新，预览会自动同步。") {
  if (currentBlocks.length > 0) {
    markPreviewStale();
  }
  if (templateStyleHint) {
    templateStyleHint.textContent = message;
  }
  queueDraftSave();
  queueHistorySnapshot();
}

function renderTemplateStyleFields() {
  if (!templateStyleTemplateSelect || !templateStyleFields) {
    return;
  }
  const templateNames = Object.keys(templateStyleDefaults);
  if (!templateStyleTemplateSelect.childElementCount) {
    templateNames.forEach((templateName) => {
      const option = document.createElement("option");
      option.value = templateName;
      option.textContent = templateDisplayName(templateName);
      templateStyleTemplateSelect.append(option);
    });
  }
  if (!activeTemplateStyleName || !templateStyleDefaults[activeTemplateStyleName]) {
    activeTemplateStyleName = templateNames[0] || "";
  }
  templateStyleTemplateSelect.value = activeTemplateStyleName;

  const fields = currentTemplateStyleDrafts[activeTemplateStyleName] || {};
  const card = document.createElement("section");
  card.className = "template-style-group";
  const title = document.createElement("h3");
  title.textContent = templateDisplayName(activeTemplateStyleName);
  const grid = document.createElement("div");
  grid.className = "template-style-grid";

  const fieldDefinitions = [
    ["background", "背景色", "color"],
    ["accent_color", "主色", "color"],
    ["title_color", "标题色", "color"],
    ["body_color", "正文字色", "color"],
    ["title_size", "标题字号", "number"],
    ["body_size", "正文字号", "number"],
    ["line_height", "行距", "number"],
    ["padding", "页边距", "number"],
    ["image_radius", "图片圆角", "number"],
  ];

  fieldDefinitions.forEach(([fieldName, labelText, inputType]) => {
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = inputType;
    input.step = fieldName === "line_height" ? "0.05" : "1";
    input.min = inputType === "number" ? "0" : "";
    input.value = String(fields[fieldName] ?? "");
    input.addEventListener("input", () => {
      currentTemplateStyleDrafts[activeTemplateStyleName][fieldName] =
        normalizeTemplateStyleValue(fieldName, input.value);
      markTemplateStyleChanged();
    });
    label.append(input);
    grid.append(label);
  });

  card.append(title, grid);
  templateStyleFields.replaceChildren(card);
}

function renderTemplateTextFields() {
  templateTextFields.replaceChildren();
  Object.entries(templateTextDefaults).forEach(([templateName, defaults]) => {
    const item = document.createElement("section");
    item.className = "template-text-item";

    const title = document.createElement("h3");
    title.textContent = templateDisplayName(templateName);

    const inputs = document.createElement("div");
    inputs.className = "template-text-inputs";

    [
      ["header_label", "顶部标签"],
      ["footer_subtitle", "底部副标题"],
    ].forEach(([fieldName, labelText]) => {
      const label = document.createElement("label");
      label.textContent = labelText;

      const input = document.createElement("input");
      input.type = "text";
      input.maxLength = 80;
      input.className = "template-text-input";
      input.value = defaults[fieldName];
      input.dataset.template = templateName;
      input.dataset.field = fieldName;
      input.setAttribute(
        "aria-label",
        `${templateDisplayName(templateName)} ${labelText}`,
      );
      input.addEventListener("focus", () => {
        activeTemplateTextInput = input;
        rememberNativeUndoTarget(input);
        applyTemplateTextButton.disabled = false;
      });
      input.addEventListener("input", () => {
        rememberNativeUndoTarget(input);
        markTemplateTextChanged();
      });

      label.append(input);
      inputs.append(label);
    });

    item.append(title, inputs);
    templateTextFields.append(item);
  });
}

function collectTemplateOverrides() {
  const overrides = {};
  templateTextFields.querySelectorAll(".template-text-input").forEach((input) => {
    const templateName = input.dataset.template;
    const fieldName = input.dataset.field;
    if (!overrides[templateName]) {
      overrides[templateName] = {};
    }
    overrides[templateName][fieldName] = input.value;
  });
  return overrides;
}

resetTemplateTextButton.addEventListener("click", () => {
  templateTextFields.querySelectorAll(".template-text-input").forEach((input) => {
    input.value =
      templateTextDefaults[input.dataset.template][input.dataset.field];
  });
  activeTemplateTextInput = null;
  templateTextHint.textContent = "已恢复全部模板的默认固定文字。";
  markTemplateTextChanged();
});

applyTemplateTextButton.addEventListener("click", () => {
  if (!activeTemplateTextInput) {
    templateTextHint.textContent =
      "请先点击一个顶部标签或底部副标题输入框，再批量应用。";
    return;
  }
  const fieldName = activeTemplateTextInput.dataset.field;
  const value = activeTemplateTextInput.value;
  templateTextFields.querySelectorAll(".template-text-input").forEach((input) => {
    if (input.dataset.field === fieldName) {
      input.value = value;
    }
  });
  const positionName =
    fieldName === "header_label" ? "顶部标签" : "底部副标题";
  templateTextHint.textContent =
    `已把“${value}”应用到全部模板的${positionName}。`;
  markTemplateTextChanged();
});

templateTextFields.addEventListener("focusin", (event) => {
  if (event.target.classList.contains("template-text-input")) {
    activeTemplateTextInput = event.target;
    rememberNativeUndoTarget(event.target);
  }
});

templateTextFields.addEventListener("click", (event) => {
  if (event.target.classList.contains("template-text-input")) {
    activeTemplateTextInput = event.target;
    rememberNativeUndoTarget(event.target);
  }
});

renderTemplateTextFields();
renderTemplateStyleFields();

templateStyleTemplateSelect?.addEventListener("change", () => {
  activeTemplateStyleName = templateStyleTemplateSelect.value;
  renderTemplateStyleFields();
});

applyTemplateStyleButton?.addEventListener("click", () => {
  if (!activeTemplateStyleName) {
    return;
  }
  const source = {...currentTemplateStyleDrafts[activeTemplateStyleName]};
  Object.keys(currentTemplateStyleDrafts).forEach((templateName) => {
    currentTemplateStyleDrafts[templateName] = {...source};
  });
  renderTemplateStyleFields();
  markTemplateStyleChanged("已把当前模板参数应用到全部模板。");
});

resetTemplateStyleButton?.addEventListener("click", () => {
  if (!activeTemplateStyleName) {
    return;
  }
  currentTemplateStyleDrafts[activeTemplateStyleName] = {
    ...templateStyleDefaults[activeTemplateStyleName],
  };
  renderTemplateStyleFields();
  markTemplateStyleChanged("已恢复当前模板默认参数。");
});

[coverEnabledInput, coverSeparatePageInput, coverPreferImageInput].forEach((input) => {
  input?.addEventListener("change", () => {
    markTemplateStyleChanged("封面设置已更新，预览会自动同步。");
  });
});

coverSubtitleInput?.addEventListener("input", () => {
  markTemplateStyleChanged("封面副标题已更新，预览会自动同步。");
});

function applyDraftTemplateOverrides(overrides) {
  if (!overrides || typeof overrides !== "object") {
    return;
  }
  templateTextFields.querySelectorAll(".template-text-input").forEach((input) => {
    const templateName = input.dataset.template;
    const fieldName = input.dataset.field;
    const value = overrides?.[templateName]?.[fieldName];
    if (typeof value === "string") {
      input.value = value;
    }
  });
}

function applyDraftTemplateStyleOverrides(overrides) {
  currentTemplateStyleDrafts = structuredClone(templateStyleDefaults);
  if (!overrides || typeof overrides !== "object") {
    renderTemplateStyleFields();
    return;
  }
  Object.entries(overrides).forEach(([templateName, fields]) => {
    if (!currentTemplateStyleDrafts[templateName] || !fields) {
      return;
    }
    Object.entries(fields).forEach(([fieldName, value]) => {
      currentTemplateStyleDrafts[templateName][fieldName] =
        normalizeTemplateStyleValue(fieldName, value);
    });
  });
  renderTemplateStyleFields();
}

function resetTemplateOverridesToDefault() {
  templateTextFields.querySelectorAll(".template-text-input").forEach((input) => {
    input.value =
      templateTextDefaults[input.dataset.template][input.dataset.field];
  });
}

function clearPreviewState() {
  Object.keys(previewCache).forEach((key) => delete previewCache[key]);
  selectedTemplates.clear();
  previewGallery.replaceChildren();
  updateSelectionUI();
}

function applySnapshotState(snapshot, options = {}) {
  const { announceRestore = false } = options;
  isRestoringSnapshot = true;
  try {
    const content = typeof snapshot.content === "string" ? snapshot.content : "";
    contentInput.value = content;
    charCount.textContent = `${content.length} 字`;

    resetTemplateOverridesToDefault();
    applyDraftTemplateOverrides(snapshot.templateOverrides);
    applyDraftTemplateStyleOverrides(snapshot.templateStyleOverrides);
    applyCoverSettings(snapshot.coverSettings);
    if (projectNameInput) {
      projectNameInput.value =
        typeof snapshot.projectName === "string" ? snapshot.projectName : "";
    }

    uploadedImages.splice(0, uploadedImages.length);
    if (Array.isArray(snapshot.uploadedImages)) {
      snapshot.uploadedImages.forEach((image) => {
        if (
          image &&
          typeof image.url === "string" &&
          typeof image.originalName === "string" &&
          typeof image.filename === "string"
        ) {
          uploadedImages.push({
            filename: image.filename,
            originalName: image.originalName,
            url: image.url,
            enabled: image.enabled !== false,
          });
        }
      });
    }
    renderUploadedImages();

    currentBlocks = Array.isArray(snapshot.blocks)
      ? snapshot.blocks
          .filter(
            (block) =>
              block &&
              typeof block.type === "string" &&
              typeof block.content === "string" &&
              block.content.trim(),
          )
          .map((block) => ({
            type: block.type,
            content: block.content,
            align: block.align === "center" ? "center" : "left",
            ...(block.type === "sticker"
              ? {
                  sticker_type: block.sticker_type || block.content || "sparkle",
                  sticker_color: /^#[0-9a-f]{6}$/i.test(block.sticker_color || "")
                    ? block.sticker_color
                    : "#D9363E",
                  sticker_size: Math.max(32, Math.min(240, Number(block.sticker_size) || 88)),
                }
              : {}),
          }))
      : [];

    clearPreviewState();

    if (currentBlocks.length > 0) {
      resultsSection.hidden = false;
      resultSummary.textContent =
        `已恢复 ${currentBlocks.length} 个草稿内容块，预览会自动同步。`;
      renderBlockEditor();
      previewDirty = true;
      if (announceRestore) {
        statusBox.textContent = "已恢复到上一步，预览会自动同步。";
        statusBox.className = "status";
      }
    } else {
      resultsSection.hidden = true;
      blockEditor.replaceChildren();
      resultSummary.textContent = "";
      previewDirty = false;
      if (announceRestore) {
        statusBox.textContent = "已清空当前草稿。";
        statusBox.className = "status";
      }
    }
    updateSelectionUI();
    queueDraftSave();
  } finally {
    isRestoringSnapshot = false;
  }
}

function clearDraftAndReset() {
  window.clearTimeout(draftSaveTimer);
  window.clearTimeout(historySaveTimer);
  localStorage.removeItem(DRAFT_STORAGE_KEY);
  historySnapshots = [];
  historyCursor = -1;
  applySnapshotState({
    content: "",
    blocks: [],
    templateOverrides: {},
    templateStyleOverrides: {},
    coverSettings: defaultCoverSettings(),
    uploadedImages: [],
    projectName: "",
  }, { announceRestore: true });
  pushHistorySnapshot();
}

function undoLastChange() {
  if (attemptNativeHistoryCommand("undo")) {
    return;
  }
  if (historyCursor <= 0) {
    return;
  }
  historyCursor -= 1;
  updateHistoryButtonState();
  applySnapshotState(JSON.parse(historySnapshots[historyCursor]), {
    announceRestore: true,
  });
}

function redoLastChange() {
  if (attemptNativeHistoryCommand("redo")) {
    return;
  }
  if (historyCursor >= historySnapshots.length - 1) {
    return;
  }
  historyCursor += 1;
  updateHistoryButtonState();
  applySnapshotState(JSON.parse(historySnapshots[historyCursor]), {
    announceRestore: true,
  });
}

function restoreDraftFromLocal() {
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) {
      return;
    }
    const draft = JSON.parse(raw);
    if (!draft || typeof draft !== "object") {
      return;
    }

    if (typeof draft.content === "string") {
      contentInput.value = draft.content;
      charCount.textContent = `${draft.content.length} 字`;
    }

    applyDraftTemplateOverrides(draft.templateOverrides);
    applySnapshotState(draft);
    if (
      (typeof draft.content === "string" && draft.content.trim()) ||
      (Array.isArray(draft.blocks) && draft.blocks.length > 0)
    ) {
      statusBox.textContent = "已自动恢复上次草稿，预览会自动同步。";
      statusBox.className = "status";
    }
    pushHistorySnapshot();
  } catch (_error) {
    // 草稿损坏时忽略恢复，避免影响页面正常使用。
  }
}

function readProjectLibrary() {
  try {
    const raw = localStorage.getItem(PROJECT_LIBRARY_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function saveProjectLibrary(items) {
  localStorage.setItem(PROJECT_LIBRARY_STORAGE_KEY, JSON.stringify(items));
}

function ensureProjectName() {
  const trimmed = projectNameInput?.value?.trim?.();
  if (trimmed) {
    return trimmed;
  }
  const fallback = `项目-${new Date().toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).replace(/[^\d]/g, "")}`;
  if (projectNameInput) {
    projectNameInput.value = fallback;
  }
  return fallback;
}

function loadProjectSnapshot(snapshot, message) {
  applySnapshotState(snapshot);
  pushHistorySnapshot();
  statusBox.textContent = message;
  statusBox.className = "status";
}

function renderProjectHistory() {
  if (!projectHistoryList) {
    return;
  }
  const items = readProjectLibrary();
  if (items.length === 0) {
    projectHistoryList.innerHTML = '<p class="upload-empty">还没有保存过项目。</p>';
    return;
  }
  projectHistoryList.replaceChildren();
  items.forEach((item) => {
    const row = document.createElement("article");
    row.className = "project-history-item";
    const meta = document.createElement("div");
    meta.className = "project-history-meta";
    const strong = document.createElement("strong");
    strong.textContent = item.name || "未命名项目";
    const span = document.createElement("span");
    span.textContent = `更新时间：${new Date(item.updatedAt || Date.now()).toLocaleString("zh-CN")}`;
    meta.append(strong, span);

    const buttons = document.createElement("div");
    buttons.className = "project-history-buttons";
    const loadButton = document.createElement("button");
    loadButton.type = "button";
    loadButton.textContent = "加载";
    loadButton.addEventListener("click", () => {
      loadProjectSnapshot(item.snapshot, `已加载项目：${item.name}`);
    });
    const renameButton = document.createElement("button");
    renameButton.type = "button";
    renameButton.textContent = "重命名";
    renameButton.addEventListener("click", () => {
      const nextName = window.prompt("请输入新的项目名", item.name || "");
      if (!nextName) {
        return;
      }
      const library = readProjectLibrary().map((entry) =>
        entry.id === item.id ? {...entry, name: nextName.trim() || entry.name} : entry,
      );
      saveProjectLibrary(library);
      renderProjectHistory();
    });
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "删除";
    deleteButton.addEventListener("click", () => {
      if (!window.confirm(`确定要删除项目「${item.name || "未命名"}」吗？删除后不可恢复。`)) {
        return;
      }
      saveProjectLibrary(readProjectLibrary().filter((entry) => entry.id !== item.id));
      renderProjectHistory();
    });
    buttons.append(loadButton, renameButton, deleteButton);
    row.append(meta, buttons);
    projectHistoryList.append(row);
  });
}

function markUploadedImagesChanged() {
  if (currentBlocks.length > 0) {
    markPreviewStale();
  }
  queueDraftSave();
  queueHistorySnapshot();
}

function collectUploadedImages() {
  return uploadedImages.map((image) => ({
    url: image.url,
    enabled: image.enabled,
  }));
}

function moveUploadedImage(index, direction) {
  const target = index + direction;
  if (target < 0 || target >= uploadedImages.length) {
    return;
  }
  [uploadedImages[index], uploadedImages[target]] = [
    uploadedImages[target],
    uploadedImages[index],
  ];
  renderUploadedImages();
  markUploadedImagesChanged();
}

async function deleteUploadedImage(index) {
  const image = uploadedImages[index];
  try {
    const response = await fetch(`/upload/${encodeURIComponent(image.filename)}`, {
      method: "DELETE",
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || "删除图片失败");
    }
    uploadedImages.splice(index, 1);
    renderUploadedImages();
    markUploadedImagesChanged();
    statusBox.textContent = `已删除图片：${image.originalName}`;
    statusBox.className = "status";
    queueHistorySnapshot();
  } catch (error) {
    statusBox.textContent = error.message;
    statusBox.className = "status error";
  }
}

function renderUploadedImages() {
  uploadedImageList.replaceChildren();
  uploadedImageCount.textContent = `${uploadedImages.length} 张`;

  if (uploadedImages.length === 0) {
    const empty = document.createElement("p");
    empty.className = "upload-empty";
    empty.textContent = "还没有上传图片。";
    uploadedImageList.append(empty);
    return;
  }

  uploadedImages.forEach((image, index) => {
    const item = document.createElement("article");
    item.className = "uploaded-image-item";
    item.classList.toggle("is-disabled", !image.enabled);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = image.enabled;
    checkbox.className = "uploaded-image-check";
    checkbox.setAttribute("aria-label", `使用图片：${image.originalName}`);
    checkbox.addEventListener("change", () => {
      image.enabled = checkbox.checked;
      item.classList.toggle("is-disabled", !image.enabled);
      markUploadedImagesChanged();
    });

    const thumbnail = document.createElement("img");
    thumbnail.className = "uploaded-image-thumb";
    thumbnail.src = image.url;
    thumbnail.alt = image.originalName;

    const info = document.createElement("div");
    info.className = "uploaded-image-info";

    const name = document.createElement("span");
    name.className = "uploaded-image-name";
    name.textContent = image.originalName;
    name.title = image.originalName;

    const placementHint = document.createElement("span");
    placementHint.className = "uploaded-image-placement";
    placementHint.textContent = "可插入任意预览页";
    info.append(name, placementHint);

    const actions = document.createElement("div");
    actions.className = "uploaded-image-actions";

    const up = document.createElement("button");
    up.type = "button";
    up.textContent = "↑";
    up.title = "上移图片";
    up.setAttribute("aria-label", `上移图片：${image.originalName}`);
    up.disabled = index === 0;
    up.addEventListener("click", () => moveUploadedImage(index, -1));

    const down = document.createElement("button");
    down.type = "button";
    down.textContent = "↓";
    down.title = "下移图片";
    down.setAttribute("aria-label", `下移图片：${image.originalName}`);
    down.disabled = index === uploadedImages.length - 1;
    down.addEventListener("click", () => moveUploadedImage(index, 1));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "删除";
    remove.className = "delete-uploaded-image";
    remove.setAttribute("aria-label", `删除图片：${image.originalName}`);
    remove.addEventListener("click", () => deleteUploadedImage(index));

    actions.append(up, down, remove);
    item.append(checkbox, thumbnail, info, actions);
    uploadedImageList.append(item);
  });
}

imageFileInput.addEventListener("change", () => {
  const file = imageFileInput.files[0];
  if (!file) {
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    statusBox.textContent = "单张图片不能超过 5MB。";
    statusBox.className = "status error";
    imageFileInput.value = "";
    return;
  }
  if (!["image/jpeg", "image/png", "image/gif", "image/webp"].includes(file.type)) {
    statusBox.textContent = "仅支持 jpg/png/gif/webp 图片。";
    statusBox.className = "status error";
    imageFileInput.value = "";
    return;
  }

  if (pendingImageObjectUrl) {
    URL.revokeObjectURL(pendingImageObjectUrl);
  }
  pendingImageFile = file;
  pendingImageObjectUrl = URL.createObjectURL(file);
  pendingImageThumb.src = pendingImageObjectUrl;
  pendingImageName.textContent = file.name;
  pendingImage.hidden = false;
  uploadImageButton.disabled = false;
});

uploadImageButton.addEventListener("click", async () => {
  if (!pendingImageFile) {
    return;
  }
  uploadImageButton.disabled = true;
  uploadImageButton.textContent = "上传中…";

  try {
    const formData = new FormData();
    formData.append("image", pendingImageFile);
    const response = await fetch("/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || "上传失败");
    }

    uploadedImages.push({
      filename: data.filename,
      originalName: data.original_name,
      url: data.url,
      enabled: true,
    });
    renderUploadedImages();
    markUploadedImagesChanged();
    statusBox.textContent = `图片已上传：${data.original_name}`;
    statusBox.className = "status";
    queueHistorySnapshot();

    URL.revokeObjectURL(pendingImageObjectUrl);
    pendingImageObjectUrl = "";
    pendingImageFile = null;
    pendingImage.hidden = true;
    pendingImageThumb.src = "";
    pendingImageName.textContent = "";
    imageFileInput.value = "";
  } catch (error) {
    statusBox.textContent = error.message;
    statusBox.className = "status error";
  } finally {
    uploadImageButton.textContent = "上传";
    uploadImageButton.disabled = pendingImageFile === null;
  }
});

renderUploadedImages();

function moveBlock(index, direction) {
  syncBlocksFromEditor();
  const target = index + direction;
  if (target < 0 || target >= currentBlocks.length) {
    return;
  }
  [currentBlocks[index], currentBlocks[target]] = [
    currentBlocks[target],
    currentBlocks[index],
  ];
  renderBlockEditor();
  markPreviewStale();
  queueHistorySnapshot();
}

function setBlockAlign(index, align) {
  const nextAlign = align === "center" ? "center" : "left";
  if (normalizedBlockAlign(currentBlocks[index]) === nextAlign) {
    return;
  }
  syncBlocksFromEditor();
  currentBlocks[index].align = nextAlign;
  renderBlockEditor();
  markPreviewStale();
  queueHistorySnapshot();
}

function updateStickerColor(index, nextColor) {
  if (!/^#[0-9a-f]{6}$/i.test(nextColor || "")) {
    return;
  }
  currentBlocks[index].sticker_color = nextColor;
  markPreviewStale();
  queueDraftSave();
  queueHistorySnapshot();
}

function updateStickerSize(index, nextSize) {
  const size = Math.max(32, Math.min(240, Number(nextSize) || 88));
  currentBlocks[index].sticker_size = size;
  markPreviewStale();
  queueDraftSave();
  queueHistorySnapshot();
}

function renderBlockEditor() {
  blockEditor.replaceChildren();
  const firstTitleIndex = currentBlocks.findIndex(
    (block) => block.type === "title",
  );

  currentBlocks.forEach((block, index) => {
    const card = document.createElement("article");
    card.className = `editor-block editor-block-${block.type}`;

    const toolbar = document.createElement("div");
    toolbar.className = "block-toolbar";

    const badge = document.createElement("span");
    badge.className = "block-type";
    badge.textContent = typeLabel(block, index, firstTitleIndex);

    const controls = document.createElement("div");
    controls.className = "move-controls";

    if (block.type !== "image") {
      ["left", "center"].forEach((align) => {
        const alignButton = document.createElement("button");
        alignButton.type = "button";
        alignButton.className = "align-toggle-button";
        alignButton.textContent = alignmentLabel(align);
        alignButton.title = `${alignmentLabel(align)}显示`;
        alignButton.setAttribute(
          "aria-label",
          `将第 ${index + 1} 段设为${alignmentLabel(align)}`,
        );
        alignButton.setAttribute(
          "aria-pressed",
          String(normalizedBlockAlign(block) === align),
        );
        alignButton.addEventListener("click", () => setBlockAlign(index, align));
        controls.append(alignButton);
      });
    }

    const upButton = document.createElement("button");
    upButton.type = "button";
    upButton.textContent = "↑";
    upButton.title = "上移这一段";
    upButton.setAttribute("aria-label", `上移第 ${index + 1} 段`);
    upButton.disabled = index === 0;
    upButton.addEventListener("click", () => moveBlock(index, -1));

    const downButton = document.createElement("button");
    downButton.type = "button";
    downButton.textContent = "↓";
    downButton.title = "下移这一段";
    downButton.setAttribute("aria-label", `下移第 ${index + 1} 段`);
    downButton.disabled = index === currentBlocks.length - 1;
    downButton.addEventListener("click", () => moveBlock(index, 1));

    controls.append(upButton, downButton);
    toolbar.append(badge, controls);

    if (block.type === "image") {
      const image = document.createElement("img");
      image.className = "editor-image-preview";
      image.src = block.content;
      image.alt = "图片内容块预览";
      card.append(toolbar, image);

      const replaceRow = document.createElement("div");
      replaceRow.className = "image-replace-row";
      const replaceInput = document.createElement("input");
      replaceInput.type = "file";
      replaceInput.accept = "image/jpeg,image/png,image/gif,image/webp";
      replaceInput.className = "image-replace-input";
      replaceInput.setAttribute("aria-label", `替换第 ${index + 1} 张图片`);
      const replaceLabel = document.createElement("label");
      replaceLabel.className = "secondary-button compact-button file-picker-button image-replace-button";
      replaceLabel.textContent = "替换图片";
      replaceLabel.append(replaceInput);
      replaceInput.addEventListener("change", async () => {
        const file = replaceInput.files[0];
        if (!file) {
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          statusBox.textContent = "单张图片不能超过 5MB。";
          statusBox.className = "status error";
          replaceInput.value = "";
          return;
        }
        try {
          const formData = new FormData();
          formData.append("image", file);
          const response = await fetch("/upload", { method: "POST", body: formData });
          const data = await response.json();
          if (!response.ok || !data.success) {
            throw new Error(data.error || "上传失败");
          }
          syncBlocksFromEditor();
          currentBlocks[index].content = data.url;
          currentBlocks[index].url = data.url;
          image.src = data.url;
          markPreviewStale();
          queueHistorySnapshot();
          statusBox.textContent = `图片已替换：${data.original_name}`;
          statusBox.className = "status";
        } catch (error) {
          statusBox.textContent = error.message;
          statusBox.className = "status error";
        } finally {
          replaceInput.value = "";
        }
      });
      replaceRow.append(replaceLabel);
      card.append(replaceRow);
      blockEditor.append(card);
      return;
    }

    if (block.type === "sticker") {
      const stickerPreview = document.createElement("div");
      stickerPreview.className = "editor-sticker-preview";
      const currentSize = normalizedStickerSize(block);
      stickerPreview.innerHTML = renderStickerSvgMarkup(
        normalizedStickerType(block),
        normalizedStickerColor(block),
        currentSize,
      );

      const stickerControls = document.createElement("div");
      stickerControls.className = "sticker-controls";

      const stickerName = document.createElement("span");
      stickerName.textContent = stickerDisplayName(block);

      const colorInput = document.createElement("input");
      colorInput.type = "color";
      colorInput.className = "sticker-color-input";
      colorInput.value = normalizedStickerColor(block);
      colorInput.setAttribute("aria-label", `修改第 ${index + 1} 个素材颜色`);
      colorInput.addEventListener("input", () => {
        updateStickerColor(index, colorInput.value);
        stickerPreview.innerHTML = renderStickerSvgMarkup(
          normalizedStickerType(currentBlocks[index]),
          normalizedStickerColor(currentBlocks[index]),
          normalizedStickerSize(currentBlocks[index]),
        );
      });

      const sizeInput = document.createElement("input");
      sizeInput.type = "range";
      sizeInput.className = "sticker-size-input";
      sizeInput.min = "32";
      sizeInput.max = "240";
      sizeInput.value = String(currentSize);
      sizeInput.setAttribute("aria-label", `修改第 ${index + 1} 个素材大小`);
      const sizeLabel = document.createElement("span");
      sizeLabel.className = "sticker-size-label";
      sizeLabel.textContent = `${currentSize}px`;
      sizeInput.addEventListener("input", () => {
        updateStickerSize(index, sizeInput.value);
        sizeLabel.textContent = `${normalizedStickerSize(currentBlocks[index])}px`;
        stickerPreview.innerHTML = renderStickerSvgMarkup(
          normalizedStickerType(currentBlocks[index]),
          normalizedStickerColor(currentBlocks[index]),
          normalizedStickerSize(currentBlocks[index]),
        );
      });

      stickerControls.append(stickerName, colorInput, sizeInput, sizeLabel);
      card.append(toolbar, stickerPreview, stickerControls);
      blockEditor.append(card);
      return;
    }

    const editor = document.createElement("div");
    editor.className = "block-content";
    editor.dataset.index = String(index);
    editor.contentEditable = "true";
    editor.spellcheck = false;
    editor.setAttribute("role", "textbox");
    editor.setAttribute("aria-multiline", "true");
    editor.setAttribute(
      "aria-label",
      `${typeLabel(block, index, firstTitleIndex)}内容`,
    );
    editor.style.textAlign = normalizedBlockAlign(block);
    setEditorMarkup(editor, block.content);
    editor.addEventListener("focus", () => {
      rememberNativeUndoTarget(editor);
    });
    editor.addEventListener("paste", (event) => {
      event.preventDefault();
      const plainText = event.clipboardData.getData("text/plain");
      document.execCommand("insertText", false, plainText);
    });
    editor.addEventListener("input", () => {
      rememberNativeUndoTarget(editor);
      currentBlocks[index].content = serializeEditor(editor);
      markPreviewStale();
      queueDraftSave();
      queueHistorySnapshot();
    });

    card.append(toolbar, editor);
    blockEditor.append(card);
  });
}

function hideInlineFormatToolbar() {
  inlineFormatToolbar.hidden = true;
  formatColorPanel.hidden = true;
  formatColorToggle.setAttribute("aria-expanded", "false");
  formatFontSize.value = "";
}

function formatValueMatches(element, property, value) {
  if (
    property === "fontWeight" &&
    (element.tagName === "STRONG" || element.tagName === "B")
  ) {
    return true;
  }
  const probe = document.createElement("span");
  probe.style[property] = value;
  return element.style[property] === probe.style[property];
}

function findFormatAncestor(node, property, value) {
  let element =
    node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
  while (element && element !== activeFormattedEditor) {
    if (formatValueMatches(element, property, value)) {
      return element;
    }
    element = element.parentElement;
  }
  return null;
}

function unwrapInlineElement(element) {
  const parent = element.parentNode;
  while (element.firstChild) {
    parent.insertBefore(element.firstChild, element);
  }
  parent.removeChild(element);
  parent.normalize();
}

function restoreInlineSelection() {
  if (!savedInlineRange || !activeFormattedEditor?.isConnected) {
    return null;
  }
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(savedInlineRange);
  return selection;
}

function updateInlineToolbarState(range) {
  const boldActive = Boolean(
    findFormatAncestor(range.commonAncestorContainer, "fontWeight", "700"),
  );
  formatBoldButton.setAttribute("aria-pressed", String(boldActive));
}

function positionInlineToolbar(rect) {
  inlineFormatToolbar.hidden = false;
  const halfWidth = inlineFormatToolbar.offsetWidth / 2;
  const left = Math.min(
    window.innerWidth - halfWidth - 10,
    Math.max(halfWidth + 10, rect.left + rect.width / 2),
  );
  const top = Math.max(
    inlineFormatToolbar.offsetHeight + 14,
    rect.top - 10,
  );
  inlineFormatToolbar.style.left = `${left}px`;
  inlineFormatToolbar.style.top = `${top}px`;
}

function applyInlineFormat(property, value) {
  const selection = restoreInlineSelection();
  if (!selection || savedInlineRange.collapsed) {
    return;
  }

  const existing = findFormatAncestor(
    savedInlineRange.commonAncestorContainer,
    property,
    value,
  );
  if (existing) {
    unwrapInlineElement(existing);
  } else {
    const span = document.createElement("span");
    span.style[property] = value;
    const fragment = savedInlineRange.extractContents();
    span.append(fragment);
    savedInlineRange.insertNode(span);
    savedInlineRange.selectNodeContents(span);
  }

  selection.removeAllRanges();
  selection.addRange(savedInlineRange);
  const index = Number(activeFormattedEditor.dataset.index);
  currentBlocks[index].content = serializeEditor(activeFormattedEditor);
  rememberNativeUndoTarget(activeFormattedEditor);
  markPreviewStale();
  queueDraftSave();
  queueHistorySnapshot();
  updateInlineToolbarState(savedInlineRange);
}

document.addEventListener("selectionchange", () => {
  if (inlineFormatToolbar.contains(document.activeElement)) {
    return;
  }
  const selection = window.getSelection();
  if (!selection || selection.rangeCount !== 1 || selection.isCollapsed) {
    hideInlineFormatToolbar();
    return;
  }

  const range = selection.getRangeAt(0);
  let node = range.commonAncestorContainer;
  if (node.nodeType !== Node.ELEMENT_NODE) {
    node = node.parentElement;
  }
  const editor = node?.closest?.(".block-content[contenteditable='true']");
  if (!editor || !blockEditor.contains(editor)) {
    hideInlineFormatToolbar();
    return;
  }

  const rect = range.getBoundingClientRect();
  if (!rect || (!rect.width && !rect.height)) {
    hideInlineFormatToolbar();
    return;
  }

  activeFormattedEditor = editor;
  savedInlineRange = range.cloneRange();
  updateInlineToolbarState(range);
  positionInlineToolbar(rect);
});

[
  formatBoldButton,
  formatColorToggle,
  ...formatColorPanel.querySelectorAll("button[data-color]"),
].forEach((button) => {
  button.addEventListener("mousedown", (event) => event.preventDefault());
});

formatBoldButton.addEventListener("click", () => {
  applyInlineFormat("fontWeight", "700");
});

formatColorToggle.addEventListener("click", () => {
  const willOpen = formatColorPanel.hidden;
  formatColorPanel.hidden = !willOpen;
  formatColorToggle.setAttribute("aria-expanded", String(willOpen));
});

formatColorPanel.querySelectorAll("button[data-color]").forEach((button) => {
  button.addEventListener("click", () => {
    applyInlineFormat("color", button.dataset.color);
    formatColorPanel.hidden = true;
    formatColorToggle.setAttribute("aria-expanded", "false");
  });
});

formatCustomColor.addEventListener("change", () => {
  applyInlineFormat("color", formatCustomColor.value);
  formatColorPanel.hidden = true;
  formatColorToggle.setAttribute("aria-expanded", "false");
});

formatFontSize.addEventListener("change", () => {
  if (formatFontSize.value) {
    applyInlineFormat("fontSize", `${formatFontSize.value}px`);
  }
  formatFontSize.value = "";
});

function replacePreviewCache(images, preserveSelection) {
  const previousSelection = new Set(selectedTemplates);
  Object.keys(previewCache).forEach((key) => delete previewCache[key]);
  images.forEach((image) => {
    if (!previewCache[image.template]) {
      previewCache[image.template] = [];
    }
    previewCache[image.template].push(image);
  });

  selectedTemplates.clear();
  Object.keys(previewCache).forEach((templateName) => {
    if (!preserveSelection || previousSelection.has(templateName)) {
      selectedTemplates.add(templateName);
    }
  });
}

function openModal(url, label) {
  modalImage.src = url;
  modalImage.alt = label;
  modalCaption.textContent = label;
  imageModal.hidden = false;
  document.body.classList.add("modal-open");
  modalClose.focus();
}

function closeModal() {
  imageModal.hidden = true;
  modalImage.src = "";
  document.body.classList.remove("modal-open");
}

function toggleTemplate(templateName) {
  if (selectedTemplates.has(templateName)) {
    selectedTemplates.delete(templateName);
  } else {
    selectedTemplates.add(templateName);
  }
  updateSelectionUI();
}

function createPreviewThumb(url, label, templateName) {
  const thumb = document.createElement("div");
  thumb.className = "preview-thumb";
  thumb.dataset.url = url;
  thumb.tabIndex = 0;
  thumb.setAttribute("role", "button");
  thumb.setAttribute("aria-label", `放大预览：${label}`);

  const image = document.createElement("img");
  image.src = url;
  image.alt = label;
  image.loading = "lazy";

  thumb.append(image);
  thumb.addEventListener("click", () => {
    toggleTemplate(templateName);
    openModal(url, label);
  });
  thumb.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleTemplate(templateName);
      openModal(url, label);
    }
  });
  return thumb;
}

function closeImagePicker() {
  imagePickerModal.hidden = true;
  activeImagePageTarget = null;
  if (imageModal.hidden) {
    document.body.classList.remove("modal-open");
  }
}

function uploadedImageName(url) {
  const uploaded = uploadedImages.find((image) => image.url === url);
  return uploaded?.originalName || url.split("/").pop() || "已插入图片";
}

function resolveImageInsertIndex(pageInfo) {
  const pageBlockStart =
    pageInfo.blockStart ?? pageInfo.block_start ?? currentBlocks.length;
  let insertIndex = Math.min(pageBlockStart, currentBlocks.length);

  // 封面页默认插在主标题下方，更接近笔记封面排版。
  if (
    pageInfo.page === 1 &&
    currentBlocks[insertIndex]?.type === "title"
  ) {
    return insertIndex + 1;
  }

  // 其他分页若页首是标题，则把图片落在标题组之后，避免贴住页顶。
  while (currentBlocks[insertIndex]?.type === "title") {
    insertIndex += 1;
  }
  return insertIndex;
}

function openImagePicker(templateName, pageInfo) {
  activeImagePageTarget = {
    templateName,
    page: pageInfo.page,
    blockStart: pageInfo.block_start,
  };
  imagePickerTarget.textContent =
    `${templateName} · 第 ${pageInfo.page} 页`;
  imagePickerList.replaceChildren();

  const availableImages = uploadedImages.filter((image) => image.enabled);
  if (availableImages.length === 0) {
    const empty = document.createElement("p");
    empty.className = "image-picker-empty";
    empty.textContent = "还没有可用图片，请先在上方“上传图片”区域上传。";
    imagePickerList.append(empty);
  } else {
    availableImages.forEach((image) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "image-picker-option";
      option.setAttribute("aria-label", `插入图片：${image.originalName}`);

      const thumbnail = document.createElement("img");
      thumbnail.src = image.url;
      thumbnail.alt = image.originalName;

      const name = document.createElement("span");
      name.textContent = image.originalName;
      option.append(thumbnail, name);
      option.addEventListener("click", async () => {
        syncBlocksFromEditor();
        const targetPage = activeImagePageTarget.page;
        const insertIndex = resolveImageInsertIndex(activeImagePageTarget);
        currentBlocks.splice(insertIndex, 0, {
          type: "image",
          content: image.url,
          url: image.url,
          width: "100%",
        });
        closeImagePicker();
        renderBlockEditor();
        await regenerateEditedPreview(
          `图片已插入第 ${targetPage} 页对应的位置。`,
        );
      });
      imagePickerList.append(option);
    });
  }

  imagePickerModal.hidden = false;
  document.body.classList.add("modal-open");
  imagePickerClose.focus();
}

function pageImageEntries(pageItem) {
  const blockStart = Number(pageItem.block_start);
  const blockEnd = Number(pageItem.block_end);
  return currentBlocks
    .map((block, index) => ({block, index}))
    .filter(
      ({block, index}) =>
        block.type === "image" &&
        index >= blockStart &&
        index <= blockEnd,
    );
}

async function removePageImage(blockIndex, pageItem) {
  syncBlocksFromEditor();
  currentBlocks.splice(blockIndex, 1);
  renderBlockEditor();
  await regenerateEditedPreview(`已删除第 ${pageItem.page} 页的图片。`);
}

async function movePageImage(blockIndex, direction, pageItem) {
  syncBlocksFromEditor();
  const pageImageIndexes = pageImageEntries(pageItem).map(({index}) => index);
  const position = pageImageIndexes.indexOf(blockIndex);
  const targetPosition = position + direction;
  if (position < 0 || targetPosition < 0 || targetPosition >= pageImageIndexes.length) {
    return;
  }
  const targetIndex = pageImageIndexes[targetPosition];
  [currentBlocks[blockIndex], currentBlocks[targetIndex]] = [
    currentBlocks[targetIndex],
    currentBlocks[blockIndex],
  ];
  renderBlockEditor();
  await regenerateEditedPreview(`第 ${pageItem.page} 页图片顺序已更新。`);
}

function createPageImageControls(pageItem) {
  const list = document.createElement("div");
  list.className = "page-inserted-images";
  const pageImages = pageImageEntries(pageItem);

  pageImages.forEach(({block, index}, position) => {
    const item = document.createElement("div");
    item.className = "page-inserted-image";

    const thumbnail = document.createElement("img");
    thumbnail.src = block.content;
    thumbnail.alt = uploadedImageName(block.content);

    const name = document.createElement("span");
    name.textContent = uploadedImageName(block.content);

    const actions = document.createElement("div");
    actions.className = "page-image-actions";

    const up = document.createElement("button");
    up.type = "button";
    up.textContent = "↑";
    up.title = "在本页上移";
    up.disabled = position === 0;
    up.addEventListener("click", () => movePageImage(index, -1, pageItem));

    const down = document.createElement("button");
    down.type = "button";
    down.textContent = "↓";
    down.title = "在本页下移";
    down.disabled = position === pageImages.length - 1;
    down.addEventListener("click", () => movePageImage(index, 1, pageItem));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "✕ 删除";
    remove.title = "删除本页图片";
    remove.addEventListener("click", () => removePageImage(index, pageItem));

    actions.append(up, down, remove);
    item.append(thumbnail, name, actions);
    list.append(item);
  });
  return list;
}

function renderPreviewCache() {
  previewGallery.replaceChildren();
  Object.entries(previewCache).forEach(([templateName, pageItems]) => {
    const group = document.createElement("article");
    group.className = "preview-template-group";
    group.dataset.template = templateName;

    const title = document.createElement("h3");
    title.textContent = templateName;
    title.title = "点击切换选择";
    title.addEventListener("click", () => toggleTemplate(templateName));

    const selector = document.createElement("label");
    selector.className = "template-selector";
    selector.title = "选择或取消这个模板";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selectedTemplates.has(templateName);
    checkbox.dataset.template = templateName;
    checkbox.setAttribute("aria-label", `选择模板：${templateName}`);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        selectedTemplates.add(templateName);
      } else {
        selectedTemplates.delete(templateName);
      }
      updateSelectionUI();
    });

    const checkmark = document.createElement("span");
    checkmark.className = "template-checkmark";
    checkmark.textContent = "✓";
    selector.append(checkbox, checkmark);

    const pages = document.createElement("div");
    pages.className = "preview-pages";
    pageItems.forEach((pageItem) => {
      const pageCard = document.createElement("div");
      pageCard.className = "preview-page-card";
      pageCard.append(
        createPreviewThumb(
          pageItem.url,
          `${templateName} · 第 ${pageItem.page} 页`,
          templateName,
        ),
      );

      const insertedImages = createPageImageControls(pageItem);
      if (insertedImages.childElementCount > 0) {
        pageCard.append(insertedImages);
      }

      const insertButton = document.createElement("button");
      insertButton.type = "button";
      insertButton.className = "insert-image-button";
      insertButton.textContent = "+ 在此页插入图片";
      insertButton.setAttribute(
        "aria-label",
        `在 ${templateName} 第 ${pageItem.page} 页插入图片`,
      );
      insertButton.addEventListener("click", () => {
        openImagePicker(templateName, pageItem);
      });
      pageCard.append(insertButton);
      pages.append(pageCard);
    });

    group.append(title, selector, pages);
    previewGallery.append(group);
  });
  updateSelectionUI();
}

function updateSelectionUI() {
  document.querySelectorAll(".preview-template-group").forEach((group) => {
    const templateName = group.dataset.template;
    const selected = selectedTemplates.has(templateName);
    group.classList.toggle("is-selected", selected);
    const checkbox = group.querySelector('input[type="checkbox"]');
    if (checkbox) {
      checkbox.checked = selected;
    }
  });

  const selectedCount = selectedTemplates.size;
  const totalCount = Object.keys(previewCache).length || 10;
  downloadSelectedButton.textContent =
    `下载选中模板 (${selectedCount}/${totalCount})`;
  downloadSelectedButton.disabled = previewDirty || selectedCount === 0;
  downloadAllButton.disabled = previewDirty || totalCount === 0;
}

modalClose.addEventListener("click", closeModal);
imagePickerClose.addEventListener("click", closeImagePicker);
imageModal.addEventListener("click", (event) => {
  if (event.target === imageModal) {
    closeModal();
  }
});
imagePickerModal.addEventListener("click", (event) => {
  if (event.target === imagePickerModal) {
    closeImagePicker();
  }
});
document.addEventListener("keydown", (event) => {
  if (
    (event.ctrlKey || event.metaKey) &&
    !event.shiftKey &&
    event.key.toLowerCase() === "z"
  ) {
    event.preventDefault();
    undoLastChange();
  } else if (
    (event.ctrlKey || event.metaKey) &&
    (
      (event.shiftKey && event.key.toLowerCase() === "z") ||
      (!event.metaKey && event.key.toLowerCase() === "y")
    )
  ) {
    event.preventDefault();
    redoLastChange();
  } else if (event.key === "Escape" && !imagePickerModal.hidden) {
    closeImagePicker();
  } else if (event.key === "Escape" && !imageModal.hidden) {
    closeModal();
  }
});

undoButton.addEventListener("mousedown", (event) => {
  event.preventDefault();
});

undoButton.addEventListener("click", () => {
  undoLastChange();
});

redoButton?.addEventListener("mousedown", (event) => {
  event.preventDefault();
});

redoButton?.addEventListener("click", () => {
  redoLastChange();
});

clearDraftButton.addEventListener("click", () => {
  clearDraftAndReset();
});

saveProjectButton?.addEventListener("click", () => {
  const name = ensureProjectName();
  const snapshot = serializeDraftState();
  const library = readProjectLibrary().filter((item) => item.name !== name);
  library.unshift({
    id: crypto.randomUUID(),
    name,
    updatedAt: Date.now(),
    snapshot,
  });
  saveProjectLibrary(library.slice(0, 20));
  renderProjectHistory();
  statusBox.textContent = `项目已保存：${name}`;
  statusBox.className = "status";
});

exportProjectButton?.addEventListener("click", () => {
  const snapshot = serializeDraftState();
  const name = ensureProjectName();
  const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
    type: "application/json",
  });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `${name}.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
});

importProjectInput?.addEventListener("change", async () => {
  const file = importProjectInput.files?.[0];
  if (!file) {
    return;
  }
  try {
    const text = await file.text();
    const snapshot = JSON.parse(text);
    loadProjectSnapshot(snapshot, `已导入项目：${file.name}`);
  } catch (_error) {
    statusBox.textContent = "导入失败：项目 JSON 格式不正确。";
    statusBox.className = "status error";
  } finally {
    importProjectInput.value = "";
  }
});

materialPresetList?.querySelectorAll(".material-preset-button").forEach((button) => {
  button.addEventListener("click", () => {
    if (currentBlocks.length === 0) {
      statusBox.textContent = "请先生成预览，再插入素材元素。";
      statusBox.className = "status error";
      return;
    }
    syncBlocksFromEditor();
    const materialType = button.dataset.material || "sparkle";
    const firstTitleIndex = currentBlocks.findIndex((block) => block.type === "title");
    const insertIndex = firstTitleIndex >= 0 ? firstTitleIndex + 1 : 0;
    currentBlocks.splice(insertIndex, 0, {
      type: "sticker",
      content: materialType,
      sticker_type: materialType,
      sticker_color: "#D9363E",
      sticker_size: 88,
      align: "center",
    });
    renderBlockEditor();
    markPreviewStale();
    queueDraftSave();
    queueHistorySnapshot();
    statusBox.textContent = `已插入素材：${STICKER_PRESET_NAMES[materialType] || "素材"}。`;
    statusBox.className = "status";
  });
});

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.success) {
    throw new Error(data.error || "操作失败，请稍后重试");
  }
  return data;
}

function validatedBlocks() {
  syncBlocksFromEditor();
  if (currentBlocks.some((block) => !block.content.trim())) {
    throw new Error("内容块不能为空，请补充内容后再试。");
  }
  return currentBlocks.map((block) => {
    const result = {
      type: block.type,
      content: block.content,
    };
    if (block.type !== "image") {
      result.align = normalizedBlockAlign(block);
    }
    if (block.type === "image") {
      result.url = block.content;
      result.width = "100%";
    }
    if (block.type === "sticker") {
      result.sticker_type = normalizedStickerType(block);
      result.sticker_color = normalizedStickerColor(block);
      result.sticker_size = normalizedStickerSize(block);
    }
    return result;
  });
}

function applyPreviewResponse(data, preserveSelection = false) {
  currentBlocks = data.blocks;
  replacePreviewCache(data.images, preserveSelection);
  renderBlockEditor();
  renderPreviewCache();
  previewDirty = false;
  updateSelectionUI();
  resultSummary.textContent =
    `已识别 ${currentBlocks.length} 个内容块，缓存 ${Object.keys(previewCache).length} 套模板、${data.images.length} 张图片。`;
  queueDraftSave();
  queueHistorySnapshot();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = contentInput.value.trim();
  if (!content) {
    statusBox.textContent = "请先粘贴笔记内容。";
    statusBox.className = "status error";
    contentInput.focus();
    return;
  }

  setInitialLoading(true);
  statusBox.textContent = "正在解析内容并生成 10 套缓存预览…";
  statusBox.className = "status";
  resultsSection.hidden = true;

  try {
    const data = await postJson("/preview", {
      content,
      template_overrides: collectTemplateOverrides(),
      template_style_overrides: collectTemplateStyleOverrides(),
      cover_settings: collectCoverSettings(),
      uploaded_images: uploadedImages.filter((image) => image.enabled !== false),
    });
    applyPreviewResponse(data, false);
    resultsSection.hidden = false;
    statusBox.textContent =
      "10 套预览已缓存。点击任意缩略图可在浮层中查看。";
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    statusBox.textContent = error.message;
    statusBox.className = "status error";
  } finally {
    setInitialLoading(false);
  }
});

async function regenerateEditedPreview(
  options = "预览缓存已更新，ZIP 也已同步刷新。",
) {
  const normalizedOptions =
    typeof options === "string" ? { successMessage: options } : options || {};
  const {
    successMessage = "预览缓存已更新，ZIP 也已同步刷新。",
    loadingMessage = "正在用调整后的内容重新生成 10 套预览…",
    silent = false,
  } = normalizedOptions;

  try {
    const blocks = validatedBlocks();
    setRefreshLoading(true);
    if (!silent) {
      statusBox.textContent = loadingMessage;
      statusBox.className = "status";
    }

    const data = await postJson("/preview", {
      blocks,
      template_overrides: collectTemplateOverrides(),
      template_style_overrides: collectTemplateStyleOverrides(),
      cover_settings: collectCoverSettings(),
      uploaded_images: uploadedImages.filter((image) => image.enabled !== false),
    });
    applyPreviewResponse(data, true);
    if (!silent) {
      statusBox.textContent = successMessage;
      statusBox.className = "status";
    }
    return true;
  } catch (error) {
    statusBox.textContent = error.message;
    statusBox.className = "status error";
    return false;
  } finally {
    setRefreshLoading(false);
  }
}

refreshButton.addEventListener("click", async () => {
  await regenerateEditedPreview();
});

async function downloadTemplates(templateNames) {
  if (previewDirty) {
    statusBox.textContent = "请先重新生成预览，让 ZIP 同步最新内容。";
    statusBox.className = "status error";
    return;
  }

  try {
    const blocks = validatedBlocks();
    setRefreshLoading(true);
    statusBox.textContent =
      `正在用编辑后的内容生成 ${templateNames.length} 套下载图片…`;
    statusBox.className = "status";

    const response = await fetch("/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        blocks,
        selected_templates: templateNames,
        template_overrides: collectTemplateOverrides(),
        template_style_overrides: collectTemplateStyleOverrides(),
        cover_settings: collectCoverSettings(),
        uploaded_images: uploadedImages.filter((image) => image.enabled !== false),
      }),
    });
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || "下载生成失败");
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download =
      templateNames.length === 10 ? "全部图片.zip" : "选中模板图片.zip";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    statusBox.textContent =
      `下载已生成：${templateNames.length} 套模板，内容来自当前编辑版本。`;
  } catch (error) {
    statusBox.textContent = error.message;
    statusBox.className = "status error";
  } finally {
    setRefreshLoading(false);
    updateSelectionUI();
  }
}

downloadSelectedButton.addEventListener("click", () => {
  if (selectedTemplates.size === 0) {
    return;
  }
  downloadTemplates(Array.from(selectedTemplates));
});

downloadAllButton.addEventListener("click", () => {
  selectedTemplates.clear();
  Object.keys(previewCache).forEach((templateName) => {
    selectedTemplates.add(templateName);
  });
  updateSelectionUI();
  downloadTemplates(Array.from(selectedTemplates));
});

restoreDraftFromLocal();
renderProjectHistory();
pushHistorySnapshot();
