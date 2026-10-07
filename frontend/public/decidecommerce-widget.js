/*!
 * DecideCommerce Widget v1.0.0
 * Klinkt sich in das Kontaktformular eines Shops ein, analysiert die Nachricht über die
 * DecideCommerce Decision API und hängt das Ergebnis als Hidden-Inputs an, bevor das
 * Formular final abgeschickt wird. Keine Abhängigkeiten, ~4 KB.
 *
 * Einbindung (vor </body>):
 *   <script src="https://app.example.com/decidecommerce-widget.js"
 *           data-api-key="dc_pk_…"                  (Publishable Key, an Domain gebunden)
 *           data-endpoint="https://api.example.com"  (Basis-URL der Decision API)
 *           data-form="#contact-form"                (optional, CSS-Selektor; sonst Auto-Erkennung)
 *           data-message-field="message"             (optional, name des Nachrichtenfelds)
 *           data-subject-field="subject"             (optional, name des Betrefffelds)
 *           data-field-prefix="dc_"                  (optional, Präfix der Hidden-Inputs)
 *           data-timeout="3000"                      (optional, ms; danach wird ohne Analyse gesendet)
 *           data-debug="true"                        (optional, Konsolen-Logs)
 *           defer></script>
 *
 * Erzeugte Hidden-Inputs (Standard-Präfix "dc_"):
 *   dc_status, dc_category, dc_urgency, dc_is_cancellation_request,
 *   dc_contains_order_number, dc_confidence, dc_analysis_id
 *
 * Das Formular wird NIE blockiert: Bei Timeout oder Fehler wird mit dc_status=error|timeout gesendet.
 */
(function () {
  "use strict";

  if (window.DecideCommerce && window.DecideCommerce.__loaded) return;

  var VERSION = "1.0.0";
  var script =
    document.currentScript || document.querySelector('script[src*="decidecommerce-widget"]');
  var data = (script && script.dataset) || {};

  var config = {
    apiKey: data.apiKey || "",
    endpoint: (data.endpoint || "").replace(/\/+$/, ""),
    formSelector: data.form || "",
    messageField: data.messageField || "",
    subjectField: data.subjectField || "",
    prefix: data.fieldPrefix || "dc_",
    timeout: parseInt(data.timeout || "3000", 10) || 3000,
    debug: data.debug === "true",
  };

  function log() {
    if (config.debug && window.console) {
      var args = Array.prototype.slice.call(arguments);
      args.unshift("[DecideCommerce]");
      console.log.apply(console, args);
    }
  }

  function warn(message) {
    if (window.console) console.warn("[DecideCommerce] " + message);
  }

  if (!config.apiKey || !config.endpoint) {
    warn("data-api-key und data-endpoint sind Pflichtattribute. Widget deaktiviert.");
    return;
  }
  if (config.apiKey.indexOf("dc_sk_") === 0) {
    warn("Secret Keys dürfen nie im Browser verwendet werden. Bitte einen Publishable Key (dc_pk_…) nutzen.");
    return;
  }

  /** Ruft die Decision API auf. Liefert das Analyse-Objekt oder wirft einen Fehler. */
  function analyze(text, options) {
    options = options || {};
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timer = setTimeout(function () {
      if (controller) controller.abort();
    }, options.timeout || config.timeout);

    var payload = { text: text };
    if (options.subject) payload.subject = String(options.subject).slice(0, 500);

    var headers = { "content-type": "application/json", "x-api-key": config.apiKey };
    if (options.idempotencyKey) headers["idempotency-key"] = options.idempotencyKey;

    return fetch(config.endpoint + "/api/v1/analyze-ticket", {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      headers: headers,
      body: JSON.stringify(payload),
      signal: controller ? controller.signal : undefined,
    })
      .then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) {
            var error = new Error((body && body.error && body.error.message) || "HTTP " + response.status);
            error.code = (body && body.error && body.error.code) || "http_error";
            throw error;
          }
          return body;
        });
      })
      .finally(function () {
        clearTimeout(timer);
      });
  }

  function getJob(jobId) {
    return fetch(config.endpoint + "/api/v1/analysis-jobs/" + encodeURIComponent(jobId), {
      method: "GET",
      mode: "cors",
      credentials: "omit",
      headers: { "x-api-key": config.apiKey },
    }).then(function (response) {
      return response.json().then(function (body) {
        if (!response.ok) {
          var error = new Error((body && body.error && body.error.message) || "HTTP " + response.status);
          error.code = (body && body.error && body.error.code) || "http_error";
          error.retryable = response.status === 429 || response.status >= 500;
          throw error;
        }
        return body;
      });
    });
  }

  function waitForJob(jobId, options) {
    options = options || {};
    var interval = options.pollInterval || 1000;
    var timeout = options.timeout == null ? 600000 : options.timeout;
    var started = Date.now();

    function poll() {
      return getJob(jobId).then(function (job) {
        if (["succeeded", "degraded", "failed"].indexOf(job.status) !== -1) return job;
        if (Date.now() - started >= timeout) {
          var error = new Error("Analyse läuft noch; später erneut abfragen.");
          error.code = "analysis_still_processing";
          throw error;
        }
        return new Promise(function (resolve) {
          setTimeout(resolve, interval);
        }).then(poll);
      }).catch(function (error) {
        if ((error && error.code && !error.retryable) || Date.now() - started >= timeout) throw error;
        return new Promise(function (resolve) {
          setTimeout(resolve, interval);
        }).then(poll);
      });
    }

    return poll();
  }

  function newIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  }

  function findField(form, name) {
    if (name) {
      var named = form.elements.namedItem(name);
      if (named && typeof named.value === "string") return named;
    }
    return null;
  }

  function findMessageField(form) {
    return findField(form, config.messageField) || form.querySelector("textarea");
  }

  function setHidden(form, name, value) {
    var fieldName = config.prefix + name;
    var input = form.querySelector('input[type="hidden"][name="' + fieldName + '"]');
    if (!input) {
      input = document.createElement("input");
      input.type = "hidden";
      input.name = fieldName;
      input.setAttribute("data-decidecommerce", "");
      form.appendChild(input);
    }
    input.value = value == null ? "" : String(value);
  }

  function applyDecision(form, result) {
    setHidden(form, "status", result.degraded ? "degraded" : "ok");
    setHidden(form, "degraded", Boolean(result.degraded));
    setHidden(form, "category", result.category);
    setHidden(form, "urgency", result.urgency);
    setHidden(form, "is_cancellation_request", result.flags.is_cancellation_request);
    setHidden(form, "contains_order_number", result.flags.contains_order_number);
    setHidden(form, "confidence", result.confidence);
    setHidden(form, "analysis_id", result.id);
    setHidden(form, "job_id", "");
    setHidden(form, "status_url", "");
    setHidden(form, "idempotency_key", "");
  }

  function applyPending(form, result, idempotencyKey) {
    setHidden(form, "status", result.status || "queued");
    [
      "category",
      "urgency",
      "is_cancellation_request",
      "contains_order_number",
      "confidence",
      "analysis_id",
      "degraded",
    ].forEach(
      function (name) {
        setHidden(form, name, "");
      },
    );
    setHidden(form, "job_id", result.id);
    setHidden(form, "status_url", result.status_url);
    setHidden(form, "idempotency_key", idempotencyKey);
  }

  function applyFailure(form, status, idempotencyKey) {
    setHidden(form, "status", status);
    [
      "category",
      "urgency",
      "is_cancellation_request",
      "contains_order_number",
      "confidence",
      "analysis_id",
      "degraded",
      "job_id",
      "status_url",
      "idempotency_key",
    ].forEach(function (name) {
      setHidden(form, name, "");
    });
    setHidden(form, "idempotency_key", idempotencyKey || "");
  }

  function isTargetForm(form) {
    if (!(form instanceof HTMLFormElement) || form.hasAttribute("data-decidecommerce-ignore")) return false;
    if (config.formSelector) return form.matches(config.formSelector);
    // Auto-Erkennung: Formulare mit Freitextfeld, aber keine Login-/Suchformulare.
    return Boolean(
      form.querySelector("textarea") &&
        !form.querySelector('input[type="password"]') &&
        form.getAttribute("role") !== "search",
    );
  }

  function resubmit(form, submitter) {
    form.__dcState = "done";
    try {
      if (typeof form.requestSubmit === "function") {
        // Löst Validierung und die eigenen Submit-Handler des Shops erneut aus.
        form.requestSubmit(submitter && submitter.form === form ? submitter : undefined);
      } else {
        HTMLFormElement.prototype.submit.call(form);
      }
    } finally {
      // AJAX-Formulare bleiben auf der Seite: nächster Versand wird erneut analysiert.
      setTimeout(function () {
        form.__dcState = "idle";
      }, 0);
    }
  }

  function onSubmit(event) {
    var form = event.target;
    if (!isTargetForm(form)) return;

    if (form.__dcState === "done") return; // unser eigener Re-Submit -> durchlassen
    if (form.__dcState === "pending") {
      event.preventDefault();
      event.stopPropagation();
      return;
    }

    var messageField = findMessageField(form);
    var text = messageField ? String(messageField.value || "").trim() : "";
    if (text.length < 3) return;

    // Abfangen, bevor Shop-eigene Handler den Versand übernehmen.
    event.preventDefault();
    event.stopPropagation();
    form.__dcState = "pending";

    var submitter = event.submitter || null;
    var subjectField = findField(form, config.subjectField);
    var started = Date.now();
    var idempotencyKey = newIdempotencyKey();
    var submitted = false;

    function submitOnce() {
      if (submitted) return;
      submitted = true;
      resubmit(form, submitter);
    }

    function handleJob(job) {
      if (job.result) {
        applyDecision(form, job.result);
        form.dispatchEvent(new CustomEvent("decidecommerce:decision", { detail: job.result, bubbles: true }));
      } else {
        var error = new Error((job.error && job.error.message) || "Analyse fehlgeschlagen.");
        applyFailure(form, "error", idempotencyKey);
        form.dispatchEvent(new CustomEvent("decidecommerce:error", { detail: error, bubbles: true }));
      }
    }

    function handleResult(result) {
      if (result && result.status_url && result.id) {
        applyPending(form, result, idempotencyKey);
        log("Analyse angenommen", result);
        form.dispatchEvent(new CustomEvent("decidecommerce:processing", { detail: result, bubbles: true }));
        submitOnce();
        waitForJob(result.id)
          .then(handleJob)
          .catch(function (error) {
            warn("Analyseergebnis noch nicht verfügbar: " + (error && error.message));
            form.dispatchEvent(new CustomEvent("decidecommerce:error", { detail: error, bubbles: true }));
          });
        return;
      }
        applyDecision(form, result);
        log("Entscheidung in " + (Date.now() - started) + " ms", result);
        form.dispatchEvent(new CustomEvent("decidecommerce:decision", { detail: result, bubbles: true }));
    }

    function reportError(error, status) {
      applyFailure(form, status, idempotencyKey);
      warn("Analyse fehlgeschlagen (" + status + "): " + (error && error.message));
      form.dispatchEvent(new CustomEvent("decidecommerce:error", { detail: error, bubbles: true }));
    }

    analyze(text, { subject: subjectField ? subjectField.value : undefined, idempotencyKey: idempotencyKey })
      .then(handleResult)
      .catch(function (error) {
        var status = error && error.name === "AbortError" ? "timeout" : "error";
        if (status !== "timeout") {
          reportError(error, status);
          return;
        }
        applyFailure(form, status, idempotencyKey);
        warn("Formular wird gesendet; Analyse wird mit demselben Idempotency-Key fortgesetzt.");
        form.dispatchEvent(
          new CustomEvent(
            "decidecommerce:processing",
            { detail: { status: "retrying", idempotencyKey: idempotencyKey }, bubbles: true },
          ),
        );
        submitOnce();
        analyze(text, {
          subject: subjectField ? subjectField.value : undefined,
          idempotencyKey: idempotencyKey,
          timeout: Math.max(config.timeout, 15000),
        })
          .then(handleResult)
          .catch(function (retryError) {
            reportError(retryError, "error");
          });
      })
      .then(submitOnce);
  }

  // Capture-Phase auf document: läuft vor allen Handlern am Formular selbst.
  document.addEventListener("submit", onSubmit, true);

  window.DecideCommerce = {
    __loaded: true,
    version: VERSION,
    /** Für eigene Integrationen (z. B. AJAX-Formulare): DecideCommerce.analyze("Text").then(...) */
    analyze: analyze,
    getJob: getJob,
    waitForJob: waitForJob,
  };

  log("Widget v" + VERSION + " aktiv", config.formSelector || "(Auto-Erkennung)");
})();
