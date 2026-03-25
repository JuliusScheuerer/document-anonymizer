/**
 * review.js — Entity selection management for the human-in-the-loop review panel.
 *
 * Vanilla JS (IIFE, no build step). Handles:
 * - Checkbox ↔ highlight bidirectional sync
 * - Tier select-all / indeterminate states
 * - Selection counter updates
 * - JSON serialization of selected entities into hidden form fields
 * - Tier collapse/expand
 * - Fetch-based PDF redaction download (binary blob via fetch + HX-Request header)
 * - Zero-selection warning before form submission
 * - Internationalized UI strings via window.__t()
 */
(function () {
  "use strict";

  // Fallback if i18n.js fails to load
  var __t = window.__t || function (key) {
    console.warn("i18n: __t not loaded, key:", key);
    return key;
  };

  var entities = [];
  var selected = {}; // index -> boolean

  function init() {
    var dataEl = document.getElementById("entities-data");
    if (!dataEl) return;

    try {
      entities = JSON.parse(dataEl.textContent);
    } catch (e) {
      console.error("Failed to parse entities data:", e);
      var panel = document.getElementById("review-panel");
      if (panel) {
        var errDiv = document.createElement("div");
        errDiv.className = "bg-red-50 border border-red-200 rounded-lg p-4";
        errDiv.textContent = __t("review.entity_load_error");
        panel.prepend(errDiv);
      }
      var anonymizeBtn = document.getElementById("anonymize-btn");
      if (anonymizeBtn) anonymizeBtn.disabled = true;
      var redactBtn = document.getElementById("redact-btn");
      if (redactBtn) redactBtn.disabled = true;
      return;
    }

    // Set initial selection: HIGH = checked, others = unchecked
    for (var i = 0; i < entities.length; i++) {
      var ent = entities[i];
      selected[ent.index] = ent.tier === "high";
    }

    bindEvents();
    syncHighlights();
    updateAllTierCheckboxes();
    persistSelection();
    updateCounter();
    syncStrategyField();
  }

  function bindEvents() {
    // Entity checkboxes
    var checkboxes = document.querySelectorAll(".entity-checkbox");
    for (var i = 0; i < checkboxes.length; i++) {
      checkboxes[i].addEventListener("change", onEntityCheckboxChange);
    }

    // Select-all checkboxes
    var selectAlls = document.querySelectorAll(".select-all-checkbox");
    for (var j = 0; j < selectAlls.length; j++) {
      selectAlls[j].addEventListener("change", onSelectAllChange);
    }

    // Tier header toggle (collapse/expand) — click or Enter/Space on header
    var tierHeaders = document.querySelectorAll("[data-tier-toggle]");
    for (var k = 0; k < tierHeaders.length; k++) {
      tierHeaders[k].addEventListener("click", onTierHeaderClick);
      tierHeaders[k].addEventListener("keydown", onTierHeaderKeydown);
    }

    // Clickable <mark> tags in preview
    var preview = document.getElementById("highlighted-preview");
    if (preview) {
      preview.addEventListener("click", onMarkClick);
    }

    // Strategy dropdown sync
    var strategySelect = document.getElementById("strategy");
    if (strategySelect) {
      strategySelect.addEventListener("change", syncStrategyField);
    }

    // HTMX: warn on zero-selection submit
    document.addEventListener("htmx:configRequest", onHtmxConfigRequest);

    // HTMX: reinit after swap (new detection results)
    document.addEventListener("htmx:afterSwap", function (e) {
      if (e.detail && e.detail.target && e.detail.target.id === "results") {
        init();
      }
    });
  }

  function onEntityCheckboxChange(e) {
    var idx = parseInt(e.target.dataset.entityIndex, 10);
    selected[idx] = e.target.checked;
    syncHighlights();
    updateTierCheckbox(tierForIndex(idx));
    persistSelection();
    updateCounter();
  }

  function onSelectAllChange(e) {
    var tier = e.target.dataset.tier;
    var checked = e.target.checked;
    toggleTier(tier, checked);
  }

  function onTierHeaderClick(e) {
    // Don't toggle collapse when clicking the checkbox itself
    if (e.target.classList.contains("select-all-checkbox")) return;
    toggleTierCollapse(e.currentTarget);
  }

  function onTierHeaderKeydown(e) {
    // Enter or Space toggles collapse (standard button behavior)
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleTierCollapse(e.currentTarget);
    }
  }

  function toggleTierCollapse(header) {
    var tier = header.dataset.tierToggle;
    var body = document.getElementById("tier-body-" + tier);
    var icon = document.getElementById("toggle-icon-" + tier);
    if (!body) return;

    var expanded = !body.hidden;
    body.hidden = expanded;
    header.setAttribute("aria-expanded", String(!expanded));
    if (icon) {
      if (expanded) {
        icon.classList.add("tier-toggle-icon--collapsed");
      } else {
        icon.classList.remove("tier-toggle-icon--collapsed");
      }
    }
  }

  function onMarkClick(e) {
    var mark = e.target.closest("mark[data-entity-index]");
    if (!mark) return;

    var idx = parseInt(mark.dataset.entityIndex, 10);
    selected[idx] = !selected[idx];

    // Sync the checkbox
    var cb = document.getElementById("entity-cb-" + idx);
    if (cb) cb.checked = selected[idx];

    syncHighlights();
    updateTierCheckbox(tierForIndex(idx));
    persistSelection();
    updateCounter();

    // Scroll the entity row into view
    var row = document.querySelector('.entity-row[data-entity-index="' + idx + '"]');
    if (row) row.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function onHtmxConfigRequest(e) {
    if (e.detail && e.detail.path === "/anonymize-form") {
      var count = countSelected();
      if (count === 0) {
        if (!confirm(__t("review.no_selection_warning"))) {
          e.preventDefault();
        }
      }
    }
  }

  function toggleTier(tier, checked) {
    for (var i = 0; i < entities.length; i++) {
      if (entities[i].tier === tier) {
        selected[entities[i].index] = checked;
        var cb = document.getElementById("entity-cb-" + entities[i].index);
        if (cb) cb.checked = checked;
      }
    }
    syncHighlights();
    updateTierCheckbox(tier);
    persistSelection();
    updateCounter();
  }

  function syncHighlights() {
    var marks = document.querySelectorAll("mark[data-entity-index]");
    for (var i = 0; i < marks.length; i++) {
      var idx = parseInt(marks[i].dataset.entityIndex, 10);
      if (selected[idx]) {
        marks[i].classList.remove("entity-highlight--deselected");
      } else {
        marks[i].classList.add("entity-highlight--deselected");
      }
    }
  }

  function updateTierCheckbox(tier) {
    var selectAll = document.getElementById("select-all-" + tier);
    if (!selectAll) return;

    var total = 0;
    var checked = 0;
    for (var i = 0; i < entities.length; i++) {
      if (entities[i].tier === tier) {
        total++;
        if (selected[entities[i].index]) checked++;
      }
    }

    if (checked === 0) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
    } else if (checked === total) {
      selectAll.checked = true;
      selectAll.indeterminate = false;
    } else {
      selectAll.checked = false;
      selectAll.indeterminate = true;
    }
  }

  function updateAllTierCheckboxes() {
    updateTierCheckbox("high");
    updateTierCheckbox("medium");
    updateTierCheckbox("low");
  }

  function persistSelection() {
    var selectedEntities = [];
    for (var i = 0; i < entities.length; i++) {
      if (selected[entities[i].index]) {
        selectedEntities.push(entities[i]);
      }
    }

    var jsonStr = JSON.stringify(selectedEntities);

    var input = document.getElementById("selected-entities-input");
    if (input) input.value = jsonStr;

    var pdfInput = document.getElementById("selected-entities-pdf");
    if (pdfInput) pdfInput.value = jsonStr;
  }

  function syncStrategyField() {
    var select = document.getElementById("strategy");
    var hidden = document.getElementById("form-strategy");
    if (select && hidden) {
      hidden.value = select.value;
    }
  }

  function updateCounter() {
    var count = countSelected();
    var total = entities.length;
    var counter = document.getElementById("selection-counter");
    if (counter) {
      counter.textContent = __t("review.entities_selected", {count: count, total: total});
    }
  }

  function countSelected() {
    var count = 0;
    for (var i = 0; i < entities.length; i++) {
      if (selected[entities[i].index]) count++;
    }
    return count;
  }

  function tierForIndex(idx) {
    for (var i = 0; i < entities.length; i++) {
      if (entities[i].index === idx) return entities[i].tier;
    }
    return "low";
  }

  /**
   * Extract plain text from an HTML error fragment returned by the server.
   * Uses DOMParser to safely parse without injecting into the live document.
   */
  function extractTextFromHtml(html) {
    try {
      var doc = new DOMParser().parseFromString(html, "text/html");
      return doc.body.textContent.trim() || __t("review.download_error");
    } catch (err) {
      console.error("Failed to parse error HTML:", err);
      return __t("review.download_error");
    }
  }

  // Fetch-based PDF redaction download.
  // Plain form POST won't send HX-Request header required by CSRF check,
  // and HTMX hx-post can't handle binary blob downloads. So we use fetch().
  function submitRedactPdf(form) {
    var formData = new FormData(form);
    var btn = form.querySelector('button[type="submit"]');
    if (btn) btn.disabled = true;

    fetch(form.action, {
      method: "POST",
      headers: { "HX-Request": "true" },
      body: formData,
    })
      .then(function (response) {
        if (!response.ok) {
          return response.text().then(function (html) {
            throw new Error(extractTextFromHtml(html));
          });
        }
        return response.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "redacted.pdf";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(function (err) {
        alert(err.message || __t("review.download_error"));
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  // Event delegation for redact-pdf forms (they may be HTMX-swapped into DOM later)
  document.addEventListener("submit", function (e) {
    var form = e.target.closest(
      "#redact-pdf-form, #redact-pdf-form-download"
    );
    if (form) {
      e.preventDefault();
      submitRedactPdf(form);
    }
  });

  // Initialize when DOM is ready or immediately if already loaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
