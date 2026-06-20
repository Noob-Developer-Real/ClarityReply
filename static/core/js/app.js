(function () {
  "use strict";

  var state = {
    method: "url",
    requestId: null,
    screenshotFile: null,
    selectedPlatform: "linkedin",
    replyStyle: "professional",
    replyLength: "medium",
    postUrl: "",
    isBusy: false
  };

  var supportedPlatforms = [
    "linkedin",
    "twitter",
    "instagram",
    "youtube",
    "reddit",
    "facebook",
    "discord",
    "whatsapp",
    "tiktok",
    "custom"
  ];

  var platformDefaults = {
    linkedin: { style: "professional", length: "medium", emoji: 20, creativity: 45 },
    twitter: { style: "engaging", length: "short", emoji: 45, creativity: 70 },
    instagram: { style: "friendly", length: "short", emoji: 75, creativity: 70 },
    youtube: { style: "engaging", length: "medium", emoji: 55, creativity: 60 },
    reddit: { style: "friendly", length: "medium", emoji: 15, creativity: 65 },
    facebook: { style: "friendly", length: "medium", emoji: 45, creativity: 55 },
    discord: { style: "friendly", length: "short", emoji: 50, creativity: 60 },
    whatsapp: { style: "friendly", length: "short", emoji: 60, creativity: 30 },
    tiktok: { style: "engaging", length: "short", emoji: 60, creativity: 80 },
    custom: { style: "professional", length: "medium", emoji: 35, creativity: 58 }
  };

  var els = {};

  document.addEventListener("DOMContentLoaded", function () {
    cacheElements();
    bindEvents();
    updateSliders();
    updatePlatformAvailability();
    autosizeTextareas();
  });

  function cacheElements() {
    els.status = document.getElementById("status-pill");
    els.toast = document.getElementById("toast");
    els.form = document.getElementById("reply-form");
    els.segments = Array.prototype.slice.call(document.querySelectorAll(".segment"));
    els.methodPanels = Array.prototype.slice.call(document.querySelectorAll(".method-panel"));
    els.urlInput = document.getElementById("source-url");
    els.extractUrlBtn = document.getElementById("extract-url-btn");
    els.uploadZone = document.getElementById("upload-zone");
    els.screenshotInput = document.getElementById("screenshot-input");
    els.imagePreview = document.getElementById("image-preview");
    els.previewImage = document.getElementById("preview-image");
    els.removeImageBtn = document.getElementById("remove-image-btn");
    els.extractImageBtn = document.getElementById("extract-image-btn");
    els.editorPanel = document.getElementById("editor-panel");
    els.settingsPanel = document.getElementById("settings-panel");
    els.resultsSection = document.getElementById("results-section");
    els.resultsGrid = document.getElementById("results-grid");
    els.skeletonGrid = document.getElementById("skeleton-grid");
    els.generateBtn = document.getElementById("generate-btn");
    els.platformField = document.getElementById("field-platform");
    els.conversationContextBlock = document.getElementById("conversation-context-block");
    els.previousMessagesField = document.getElementById("previous-messages");
    els.authorNameField = document.getElementById("field-author-name");
    els.authorUsernameField = document.getElementById("field-author-username");
    els.titleField = document.getElementById("field-title");
    els.summaryField = document.getElementById("field-summary");
    els.contentField = document.getElementById("field-content");
    els.platformChips = Array.prototype.slice.call(document.querySelectorAll("#platform-chips .chip"));
    els.styleButtons = Array.prototype.slice.call(document.querySelectorAll("#style-segments button"));
    els.lengthButtons = Array.prototype.slice.call(document.querySelectorAll("#length-segments button"));
    els.emojiSlider = document.getElementById("emoji-level");
    els.creativitySlider = document.getElementById("creativity-level");
    els.emojiOutput = document.getElementById("emoji-output");
    els.creativityOutput = document.getElementById("creativity-output");
    els.progressDots = Array.prototype.slice.call(document.querySelectorAll("[data-progress-dot]"));
  }

  function bindEvents() {
    els.segments.forEach(function (button) {
      button.addEventListener("click", function () {
        setMethod(button.dataset.method);
      });
    });

    els.extractUrlBtn.addEventListener("click", extractFromUrl);
    els.extractImageBtn.addEventListener("click", extractFromScreenshot);
    els.form.addEventListener("submit", generateReplies);

    els.uploadZone.addEventListener("click", function () {
      els.screenshotInput.click();
    });

    els.screenshotInput.addEventListener("change", function () {
      setScreenshotFile(els.screenshotInput.files[0] || null);
    });

    ["dragenter", "dragover"].forEach(function (eventName) {
      els.uploadZone.addEventListener(eventName, function (event) {
        event.preventDefault();
        els.uploadZone.classList.add("is-dragging");
      });
    });

    ["dragleave", "drop"].forEach(function (eventName) {
      els.uploadZone.addEventListener(eventName, function (event) {
        event.preventDefault();
        els.uploadZone.classList.remove("is-dragging");
      });
    });

    els.uploadZone.addEventListener("drop", function (event) {
      setScreenshotFile(event.dataTransfer.files[0] || null);
    });

    els.removeImageBtn.addEventListener("click", function () {
      setScreenshotFile(null);
    });

    Array.prototype.slice.call(document.querySelectorAll("textarea")).forEach(function (textarea) {
      textarea.addEventListener("input", function () {
        autosize(textarea);
      });
    });

    els.platformChips.forEach(function (button) {
      button.addEventListener("click", function () {
        setPlatform(button.dataset.platform, true);
      });
    });

    els.platformField.addEventListener("change", function () {
      setPlatform(els.platformField.value, true);
    });

    bindRadioGroup(els.styleButtons, function (value) {
      state.replyStyle = value;
    });

    bindRadioGroup(els.lengthButtons, function (value) {
      state.replyLength = value;
    });

    [els.emojiSlider, els.creativitySlider].forEach(function (slider) {
      slider.addEventListener("input", updateSliders);
    });
  }

  function setMethod(method) {
    state.method = method;
    els.segments.forEach(function (button) {
      var isActive = button.dataset.method === method;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", String(isActive));
    });
    els.methodPanels.forEach(function (panel) {
      panel.classList.toggle("is-active", panel.dataset.panel === method);
    });
    updatePlatformAvailability();
  }

  function bindRadioGroup(buttons, onChange) {
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        buttons.forEach(function (item) {
          var isActive = item === button;
          item.classList.toggle("is-active", isActive);
          item.setAttribute("aria-checked", String(isActive));
        });
        onChange(button.dataset.value);
      });
    });
  }

  function setScreenshotFile(file) {
    if (!file) {
      state.screenshotFile = null;
      els.screenshotInput.value = "";
      els.imagePreview.hidden = true;
      els.previewImage.removeAttribute("src");
      return;
    }

    if (!/^image\/(png|jpe?g|webp|gif)$/i.test(file.type)) {
      showToast("Upload a PNG, JPG, WEBP, or GIF screenshot.", true);
      return;
    }

    state.screenshotFile = file;
    els.previewImage.src = URL.createObjectURL(file);
    els.imagePreview.hidden = false;
  }

  function autosizeTextareas() {
    Array.prototype.slice.call(document.querySelectorAll("textarea")).forEach(autosize);
  }

  function autosize(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.max(textarea.scrollHeight, 132) + "px";
  }

  function updateSliders() {
    updateSlider(els.emojiSlider, els.emojiOutput);
    updateSlider(els.creativitySlider, els.creativityOutput);
  }

  function updateSlider(slider, output) {
    var value = Number(slider.value);
    var min = Number(slider.min || 0);
    var max = Number(slider.max || 100);
    var percent = ((value - min) / (max - min)) * 100;
    slider.style.setProperty("--fill", percent + "%");
    output.textContent = String(value);
  }

  function setPlatform(platform, applyDefaults) {
    platform = normalizePlatform(platform);
    if (state.method === "url" && isConversationPlatform(platform)) {
      platform = "linkedin";
    }
    state.selectedPlatform = platform;
    els.platformField.value = platform;
    els.platformChips.forEach(function (button) {
      var selected = button.dataset.platform === platform;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-checked", String(selected));
    });
    updateConversationContextVisibility(platform);
    updateEditorVisibility();
    if (applyDefaults) {
      applyPlatformDefaults(platform);
    }
  }

  function isConversationPlatform(platform) {
    return platform === "discord" || platform === "whatsapp";
  }

  function updatePlatformAvailability() {
    var allowConversationPlatforms = state.method === "screenshot";
    els.platformChips.forEach(function (button) {
      var isConversationChip = isConversationPlatform(button.dataset.platform);
      button.hidden = isConversationChip && !allowConversationPlatforms;
    });
    if (!allowConversationPlatforms && isConversationPlatform(state.selectedPlatform)) {
      setPlatform("linkedin", true);
    }
  }

  function updateConversationContextVisibility(platform) {
    var shouldShow = isConversationPlatform(platform);
    els.conversationContextBlock.hidden = !shouldShow;
    if (!shouldShow) {
      els.previousMessagesField.value = "";
    }
  }

  function updateEditorVisibility() {
    var shouldHideEditor = isConversationPlatform(state.selectedPlatform);
    els.editorPanel.hidden = shouldHideEditor;
    els.editorPanel.classList.toggle("is-visible", !shouldHideEditor);
  }

  function applyPlatformDefaults(platform) {
    var defaults = platformDefaults[platform] || platformDefaults.custom;
    setRadioValue(els.styleButtons, defaults.style);
    setRadioValue(els.lengthButtons, defaults.length);
    state.replyStyle = defaults.style;
    state.replyLength = defaults.length;
    els.emojiSlider.value = String(defaults.emoji);
    els.creativitySlider.value = String(defaults.creativity);
    updateSliders();
  }

  function setRadioValue(buttons, value) {
    buttons.forEach(function (button) {
      var isActive = button.dataset.value === value;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-checked", String(isActive));
    });
  }

  function showWorkspace() {
    els.settingsPanel.hidden = false;
    els.settingsPanel.classList.add("is-visible");
    updateEditorVisibility();
    setProgress("edit");
    setStatus("Context ready");
    window.requestAnimationFrame(function () {
      autosizeTextareas();
    });
  }

  function setProgress(step) {
    els.progressDots.forEach(function (dot) {
      var name = dot.dataset.progressDot;
      dot.classList.toggle("is-active", name === "input" || name === step || (step === "results" && name === "edit"));
    });
  }

  async function extractFromUrl() {
    var url = els.urlInput.value.trim();
    if (!url) {
      showToast("Paste a social media URL first.", true);
      els.urlInput.focus();
      return;
    }
    state.postUrl = url;

    await withButtonLoading(els.extractUrlBtn, async function () {
      setStatus("Extracting URL");
      console.log("[EXTRACT][FRONTEND] Sending /api/extract/ URL request", {
        source_type: "url",
        url: url,
        platform: state.selectedPlatform
      });
      var response = await apiFetch("/api/extract/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_type: "url",
          url: url,
          platform: state.selectedPlatform
        })
      });

      applyExtraction(response);
      showToast("Content extracted. Review the details below.");
    });
  }

  async function extractFromScreenshot() {
    if (!state.screenshotFile) {
      showToast("Upload a screenshot first.", true);
      return;
    }

    var formData = new FormData();
    formData.append("source_type", "screenshot");
    formData.append("platform", state.selectedPlatform);
    formData.append("image", state.screenshotFile);

    await withButtonLoading(els.extractImageBtn, async function () {
      setStatus("Reading screenshot");
      var response = await apiFetch("/api/extract/", {
        method: "POST",
        body: formData
      });

      applyExtraction(response);
      showToast("Screenshot extracted. Review the details below.");
    });
  }

  function applyExtraction(response) {
    console.log("[EXTRACT][FRONTEND] Raw /api/extract/ response", response);
    state.requestId = response.request_id || null;
    var data = response.platform_present_data || response.platform_present || response.platform_data || response.data || {};
    state.postUrl = data.url || state.postUrl || "";
    console.log("[EXTRACT][FRONTEND] Data object selected for form mapping", data);
    if (data.platform) {
      state.selectedPlatform = normalizePlatform(data.platform);
    }
    fillEditor(data);
    showWorkspace();
  }

  function fillEditor(data) {
    var platform = normalizePlatform(data.platform || state.selectedPlatform || "custom");
    console.log("[EXTRACT][FRONTEND] Filling editor fields", {
      platform: platform,
      author_name: data.author_name || "",
      author_username: data.author_username || "",
      title: data.title || "",
      summary: data.summary || "",
      content: data.content || data.ocr_text || ""
    });
    els.platformField.value = platform;
    els.authorNameField.value = data.author_name || "";
    els.authorUsernameField.value = data.author_username || "";
    els.titleField.value = data.title || "";
    els.summaryField.value = data.summary || "";
    els.contentField.value = data.content || data.ocr_text || "";
    setPlatform(platform, true);
    autosizeTextareas();
  }

  async function generateReplies(event) {
    event.preventDefault();

    var content = els.contentField.value.trim();
    if (!content) {
      showToast("Extract content before generating.", true);
      return;
    }

    var payload = {
      selected_template: state.selectedPlatform,
      platform: state.selectedPlatform,
      title: els.titleField.value.trim(),
      content: content,
      summary: els.summaryField.value.trim(),
      author_name: els.authorNameField.value.trim(),
      author_username: els.authorUsernameField.value.trim(),
      reply_goal: "engage",
      reply_style: state.replyStyle,
      reply_length: state.replyLength,
      emoji_level: Number(els.emojiSlider.value),
      creativity_level: Number(els.creativitySlider.value)
    };

    if (state.selectedPlatform === "discord" || state.selectedPlatform === "whatsapp") {
      payload.previous_messages = els.previousMessagesField.value.trim();
    }

    if (state.requestId) {
      payload.request_id = state.requestId;
    } else {
      payload.post_content = content;
    }

    await withButtonLoading(els.generateBtn, async function () {
      setStatus("Generating replies");
      showSkeletons(true);
      var response = await apiFetch("/api/generate-reply/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      state.requestId = response.request_id || state.requestId;
      renderResults(response);
      showSkeletons(false);
      setProgress("results");
      setStatus("Replies ready");
      showToast("Replies generated.");
    }, function () {
      showSkeletons(false);
    });
  }

  function renderResults(response) {
    var replies = [
      {
        title: "Variation 1",
        text: response.variation_1 || ""
      },
      {
        title: "Variation 2",
        text: response.variation_2 || ""
      },
      {
        title: "Variation 3",
        text: response.variation_3 || ""
      }
    ];

    els.resultsGrid.innerHTML = replies.map(function (reply, index) {
      var safeText = escapeHtml(reply.text || "No reply returned.");
      var words = countWords(reply.text);
      return [
        '<article class="result-card">',
        '  <div class="result-header">',
        "    <h4>" + escapeHtml(reply.title) + "</h4>",
        '    <button class="copy-button" type="button" data-copy-index="' + index + '">Copy</button>',
        "  </div>",
        '  <p class="reply-text">' + safeText + "</p>",
        '  <span class="word-count">' + words + " word" + (words === 1 ? "" : "s") + "</span>",
        "</article>"
      ].join("");
    }).join("");

    els.resultsSection.hidden = false;
    els.resultsSection.classList.add("is-visible");
    els.resultsGrid.querySelectorAll("[data-copy-index]").forEach(function (button) {
      button.addEventListener("click", function () {
        var reply = replies[Number(button.dataset.copyIndex)].text || "";
        copyReply(button, reply, state.postUrl);
      });
    });
    els.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function copyReply(button, text, postUrl) {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
      button.classList.add("is-copied");
      showToast("Reply copied.");
      if (postUrl) {
        window.open(postUrl, "_blank");
      }
      window.setTimeout(function () {
        button.textContent = "Copy";
        button.classList.remove("is-copied");
      }, 1500);
    } catch (error) {
      showToast("Copy failed. Select the text and copy manually.", true);
    }
  }

  async function apiFetch(url, options) {
    try {
      var response = await fetch(url, options);
      var data = await response.json().catch(function () {
        return {};
      });
      console.log("[EXTRACT][FRONTEND] Fetch completed", {
        url: url,
        status: response.status,
        ok: response.ok,
        json: data
      });

      if (!response.ok || data.success === false) {
        throw new Error(data.error || "Request failed. Please try again.");
      }

      return data;
    } catch (error) {
      showToast(error.message || "Network failure. Please try again.", true);
      setStatus("Needs attention");
      throw error;
    }
  }

  async function withButtonLoading(button, work, onError) {
    if (state.isBusy) {
      return;
    }

    state.isBusy = true;
    button.disabled = true;
    button.classList.add("is-loading");

    try {
      await work();
    } catch (error) {
      if (onError) {
        onError(error);
      }
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
      state.isBusy = false;
    }
  }

  function showSkeletons(show) {
    els.resultsSection.hidden = false;
    els.resultsSection.classList.add("is-visible");
    els.skeletonGrid.hidden = !show;
    els.resultsGrid.hidden = show;
    if (show) {
      els.resultsGrid.innerHTML = "";
      els.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function setStatus(text) {
    els.status.textContent = text;
  }

  function showToast(message, isError) {
    els.toast.textContent = message;
    els.toast.classList.toggle("is-error", Boolean(isError));
    els.toast.classList.add("is-visible");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(function () {
      els.toast.classList.remove("is-visible");
    }, 3600);
  }

  function normalizePlatform(value) {
    var normalized = String(value || "custom").trim().toLowerCase();
    var map = {
      x: "twitter",
      "twitter/x": "twitter"
    };
    normalized = map[normalized] || normalized;
    return supportedPlatforms.indexOf(normalized) === -1 ? "custom" : normalized;
  }

  function countWords(text) {
    return String(text || "").trim().split(/\s+/).filter(Boolean).length;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
})();
