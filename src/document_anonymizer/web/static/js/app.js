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

  // Example text: load sample PII into textarea
  var EXAMPLE_TEXT =
    "Sehr geehrte Damen und Herren,\n\n" +
    "mein Name ist Dr. Matthias Bergmann und ich schreibe Ihnen bezüglich meines Vertrags.\n" +
    "Meine Kontaktdaten lauten wie folgt:\n\n" +
    "  Name:           Dr. Matthias Bergmann\n" +
    "  Geburtsdatum:   14.03.1987\n" +
    "  Anschrift:      Schillerstraße 42, 80336 München\n" +
    "  Telefon:        +49 89 12345678\n" +
    "  Mobilnummer:    0171 9876543\n" +
    "  E-Mail:         matthias.bergmann@beispiel.de\n\n" +
    "  Steuer-ID:      12 345 678 901\n" +
    "  Personalausweis: T220001293\n" +
    "  IBAN:           DE89 3704 0044 0532 0130 00\n\n" +
    "  Handelsregister: HRB 12345 B\n\n" +
    "Mit freundlichen Grüßen,\n" +
    "Dr. Matthias Bergmann";

  document.addEventListener("click", function (e) {
    if (!e.target || e.target.id !== "load-example-btn") return;
    e.preventDefault();
    var textarea = document.getElementById("text");
    if (textarea) {
      textarea.value = EXAMPLE_TEXT;
      textarea.focus();
      e.target.textContent = "Geladen!";
    } else {
      e.target.textContent = "Fehler!";
    }
    setTimeout(function () {
      e.target.textContent = "Beispieltext laden";
    }, 1500);
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
