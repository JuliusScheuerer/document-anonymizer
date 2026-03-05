/**
 * i18n.js — Client-side translation helper.
 *
 * Provides window.__t(key, replacements) for looking up translations
 * set by the server via window.__translations.
 * Placeholders use {name} format. All occurrences of each placeholder
 * are replaced (matching server-side str.format() behavior).
 */
(function () {
  "use strict";

  window.__t = function (key, replacements) {
    var translations = window.__translations;
    if (!translations || typeof translations !== "object") {
      console.warn("i18n: window.__translations not loaded, key:", key);
      return key;
    }
    var template = translations[key];
    if (template === undefined) {
      console.warn("i18n: missing translation key:", key);
      return key;
    }
    if (replacements) {
      var keys = Object.keys(replacements);
      for (var i = 0; i < keys.length; i++) {
        template = template.split("{" + keys[i] + "}").join(String(replacements[keys[i]]));
      }
    }
    return template;
  };
})();
