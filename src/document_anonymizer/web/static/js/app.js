/**
 * app.js — Shared event handlers (migrated from inline scripts for CSP compliance).
 */
(function () {
  "use strict";

  // Range slider: sync displayed value on input
  document.addEventListener("input", function (e) {
    if (e.target && e.target.id === "score_threshold") {
      var display = document.getElementById("threshold-value");
      if (display) {
        display.textContent = parseFloat(e.target.value).toFixed(2);
      }
    }
  });

  // Copy button: copy anonymized text to clipboard
  document.addEventListener("click", function (e) {
    var btn = e.target;
    if (!btn || btn.id !== "copy-btn") return;

    var panel = document.querySelector(".diff-anonymized");
    if (!panel) return;

    var text = panel.textContent;
    var originalLabel = btn.textContent;

    function showFeedback() {
      btn.textContent = "Kopiert!";
      setTimeout(function () {
        btn.textContent = originalLabel;
      }, 2000);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(showFeedback).catch(function () {
        btn.textContent = "Kopieren fehlgeschlagen";
        setTimeout(function () { btn.textContent = originalLabel; }, 3000);
      });
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      var success = document.execCommand("copy");
      document.body.removeChild(ta);
      if (success) {
        showFeedback();
      } else {
        btn.textContent = "Kopieren fehlgeschlagen";
        setTimeout(function () { btn.textContent = originalLabel; }, 3000);
      }
    }
  });
})();
