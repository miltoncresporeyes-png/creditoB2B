(function () {
  "use strict";

  var M = window.CreditModel;
  if (!M) return;

  // Si corre en Hostinger o dominio externo, apuntar a Railway; si corre en local o mismo host, usar ruta relativa
  var API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname.endsWith('railway.app'))
    ? ''
    : 'https://creditob2b-production.up.railway.app';

  var $ = function (id) { return document.getElementById(id); };
  var form = $("creditForm");
  var results = $("results");
  var btnPrint = $("btnPrint");
  var helpModal = $("helpModal");
  var draftNotice = $("draftNotice");
  var draftText = $("draftText");
  var toast = $("toast");
  var LAST_RESULT = null;
  var CURRENT_EVAL_ID = null;
  var CURRENT_MODE = "manual"; // 'manual' (gratuita) o 'automated' (documental de pago)
  var urlParams = new URLSearchParams(window.location.search);
  var urlCreditToken = urlParams.get("credit_token");
  if (urlCreditToken) {
    localStorage.setItem("creditob2b_active_token", urlCreditToken.trim());
    // Limpiar inmediatamente el token de la URL visible para evitar fugas en historial, bookmarks o Referer
    urlParams.delete("credit_token");
    var cleanSearch = urlParams.toString();
    var cleanUrl = window.location.pathname + (cleanSearch ? "?" + cleanSearch : "");
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", cleanUrl);
    }
  }
  var ACTIVE_CREDIT_TOKEN = localStorage.getItem("creditob2b_active_token") || "";
  var saveTimer = null;
  var toastTimer = null;
  var extractedExtra = {};
  var STORAGE_KEY = "credit-eval-draft-v1";
  var REQUIRED_DOCS = M.REQUIRED_DOCS;

  var EXAMPLE_PROFILES = {
    aprobado: {
      razonSocial: "Andes Tecnología SpA",
      rut: "76.543.210-3",
      rutERut: "76.543.210-3",
      rutSolicitante: "12.345.678-5",
      representantes: "12.345.678-5\n9.876.543-3",
      sector: "servicios_ti",
      antiguedad: 8,
      ventas12m: 1200000000,
      montoSolicitado: 50000000,
      plazo: "60",
      exposicionActual: 12000000,
      concentracionTopCliente: 25,
      activoCorriente: 320000000,
      pasivoCorriente: 180000000,
      inventarios: 30000000,
      caja: 40000000,
      cuentasPorCobrar: 180000000,
      ebitda: 150000000,
      flujoCajaOperacional: 110000000,
      gastosFinancieros: 18000000,
      servicioDeuda: 35000000,
      pasivoTotal: 380000000,
      patrimonio: 300000000,
      deudaFinanciera: 120000000,
      deudaFinancieraCP: 30000000,
      maxDiasMora: 0,
      deudaVencida: 0,
      deudaCastigada: 0,
      instituciones: 2,
      protestos: 0,
      morosidades: 0,
      montoMorosidades: 0,
      pagoHistorico: "puntual",
      facturasVencidas: 0,
      situacionTributaria: "ok",
      deudaTGR: 0,
      f29SinDeclarar: 0,
      tendenciaVentas: "sube",
      docTribOk: true,
      docERutOk: true,
      docCMFOk: true,
      docEscrituraOk: true,
      docEEFFOk: true,
      docDicomOk: true,
      inicioVigente: "1",
      sociedadVigente: true,
      facultades: true,
      eeccVerificados: true,
      aval: false,
      garantia: false,
      seguroCredito: true,
      limitePoliticaRiesgo: 80000000,
      factorComercial: 0.9,
      multiplicadorFlujo: 1,
      validacionLegal: true,
      autorizacion90: false,
      justificacion90: false,
      analista: "Milton Crespo (Analista Senior)",
      observaciones: "Ejemplo demostrativo: Empresa TI con liquidez sólida (Razón Corriente 1.78x), flujo operacional positivo, CMF sin moras y cobertura de intereses holgada."
    },
    industrial: {
      razonSocial: "Manufacturas & Metales del Sur S.A.",
      rut: "96.812.440-K",
      rutERut: "96.812.440-K",
      rutSolicitante: "14.220.518-2",
      representantes: "14.220.518-2\n11.903.415-9\n8.751.203-1",
      sector: "manufactura",
      antiguedad: 14,
      ventas12m: 3400000000,
      montoSolicitado: 120000000,
      plazo: "90",
      exposicionActual: 35000000,
      concentracionTopCliente: 18,
      activoCorriente: 1100000000,
      pasivoCorriente: 620000000,
      inventarios: 380000000,
      caja: 95000000,
      cuentasPorCobrar: 540000000,
      ebitda: 420000000,
      flujoCajaOperacional: 310000000,
      gastosFinancieros: 45000000,
      servicioDeuda: 92000000,
      pasivoTotal: 1250000000,
      patrimonio: 1180000000,
      deudaFinanciera: 480000000,
      deudaFinancieraCP: 110000000,
      maxDiasMora: 0,
      deudaVencida: 0,
      deudaCastigada: 0,
      instituciones: 4,
      protestos: 0,
      morosidades: 0,
      montoMorosidades: 0,
      pagoHistorico: "puntual",
      facturasVencidas: 0,
      situacionTributaria: "ok",
      deudaTGR: 0,
      f29SinDeclarar: 0,
      tendenciaVentas: "sube",
      docTribOk: true,
      docERutOk: true,
      docCMFOk: true,
      docEscrituraOk: true,
      docEEFFOk: true,
      docDicomOk: true,
      inicioVigente: "1",
      sociedadVigente: true,
      facultades: true,
      eeccVerificados: true,
      aval: true,
      garantia: true,
      seguroCredito: true,
      limitePoliticaRiesgo: 150000000,
      factorComercial: 0.95,
      multiplicadorFlujo: 1.2,
      validacionLegal: true,
      autorizacion90: true,
      justificacion90: true,
      analista: "Comité de Riesgo Industrial",
      observaciones: "Ejemplo demostrativo: Empresa manufacturera con 14 años en el mercado, rotación de inventarios periódica, plazo 90 días respaldado con garantías reales y fianza solidaria."
    },
    observado: {
      razonSocial: "Distribuidora Comercial Horizonte Ltda.",
      rut: "77.340.910-4",
      rutERut: "77.340.910-4",
      rutSolicitante: "15.840.119-7",
      representantes: "15.840.119-7",
      sector: "distribucion_mayorista",
      antiguedad: 3.5,
      ventas12m: 650000000,
      montoSolicitado: 45000000,
      plazo: "60",
      exposicionActual: 18000000,
      concentracionTopCliente: 42,
      activoCorriente: 130000000,
      pasivoCorriente: 115000000,
      inventarios: 55000000,
      caja: 8000000,
      cuentasPorCobrar: 62000000,
      ebitda: 32000000,
      flujoCajaOperacional: 14000000,
      gastosFinancieros: 12000000,
      servicioDeuda: 21000000,
      pasivoTotal: 185000000,
      patrimonio: 45000000,
      deudaFinanciera: 75000000,
      deudaFinancieraCP: 35000000,
      maxDiasMora: 22,
      deudaVencida: 3200000,
      deudaCastigada: 0,
      instituciones: 2,
      protestos: 1,
      morosidades: 1,
      montoMorosidades: 2100000,
      pagoHistorico: "atraso_leve",
      facturasVencidas: 1800000,
      situacionTributaria: "esp",
      deudaTGR: 1450000,
      f29SinDeclarar: 1,
      tendenciaVentas: "estable",
      docTribOk: true,
      docERutOk: true,
      docCMFOk: true,
      docEscrituraOk: true,
      docEEFFOk: true,
      docDicomOk: true,
      inicioVigente: "1",
      sociedadVigente: true,
      facultades: true,
      eeccVerificados: false,
      aval: true,
      garantia: false,
      seguroCredito: false,
      limitePoliticaRiesgo: 20000000,
      factorComercial: 0.75,
      multiplicadorFlujo: 0.8,
      validacionLegal: true,
      autorizacion90: false,
      justificacion90: false,
      analista: "Unidad de Control Crediticio",
      observaciones: "Ejemplo demostrativo: Perfil con mora bancaria CMF de 22 días, 1 protesto pendiente en boletín comercial y deuda en TGR. Permite observar cómo el modelo calcula advertencias y acota el monto recomendado."
    }
  };

  var EXAMPLE = EXAMPLE_PROFILES.aprobado;

  function esc(value) {
    return String(value === null || value === undefined ? "" : value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  function collectForm() {
    var data = {};
    form.querySelectorAll("input, select, textarea").forEach(function (field) {
      if (!field.id || field.type === "file") return;
      data[field.id] = field.type === "checkbox" ? field.checked : field.value;
    });
    return data;
  }

  function toModelInput(data) {
    return {
      razonSocial: data.razonSocial,
      rut: data.rut,
      rutERut: data.rutERut,
      rutSolicitante: data.rutSolicitante,
      representantes: data.representantes,
      sector: data.sector,
      antiguedad: data.antiguedad,
      ventas12m: data.ventas12m,
      montoSolicitado: data.montoSolicitado,
      plazo: data.plazo,
      exposicionActual: data.exposicionActual,
      concentracionTopCliente: data.concentracionTopCliente,
      activoCorriente: data.activoCorriente,
      pasivoCorriente: data.pasivoCorriente,
      inventarios: data.inventarios,
      caja: data.caja,
      cuentasPorCobrar: data.cuentasPorCobrar,
      ebitda: data.ebitda,
      flujoCajaOperacional: data.flujoCajaOperacional,
      gastosFinancieros: data.gastosFinancieros,
      servicioDeuda: data.servicioDeuda,
      pasivoTotal: data.pasivoTotal,
      patrimonio: data.patrimonio,
      deudaFinanciera: data.deudaFinanciera,
      deudaFinancieraCP: data.deudaFinancieraCP,
      deudaSociosRelacionados: extractedExtra.deudaSociosRelacionados,
      diferenciaCambio: extractedExtra.diferenciaCambio,
      maxDiasMora: data.maxDiasMora,
      deudaVencida: data.deudaVencida,
      deudaCastigada: data.deudaCastigada,
      instituciones: data.instituciones,
      protestos: data.protestos,
      morosidades: data.morosidades,
      montoMorosidades: data.montoMorosidades,
      pagoHistorico: data.pagoHistorico,
      facturasVencidas: data.facturasVencidas,
      situacionTributaria: data.situacionTributaria,
      deudaTGR: data.deudaTGR,
      f29SinDeclarar: data.f29SinDeclarar,
      tendenciaVentas: data.tendenciaVentas,
      docs: {
        trib: !!data.docTribOk,
        erut: !!data.docERutOk,
        cmf: !!data.docCMFOk,
        escritura: !!data.docEscrituraOk,
        eecc: !!data.docEEFFOk,
        dicom: !!data.docDicomOk
      },
      inicioVigente: data.inicioVigente,
      sociedadVigente: data.sociedadVigente,
      facultades: data.facultades,
      eeccVerificados: data.eeccVerificados,
      aval: data.aval,
      garantia: data.garantia,
      seguroCredito: data.seguroCredito,
      limitePoliticaRiesgo: data.limitePoliticaRiesgo,
      factorComercial: data.factorComercial,
      multiplicadorFlujo: data.multiplicadorFlujo,
      validacionLegal: data.validacionLegal,
      autorizacion90: data.autorizacion90,
      justificacion90: data.justificacion90,
      analista: data.analista,
      observaciones: data.observaciones
    };
  }

  function populateSelects() {
    var sector = $("sector");
    Object.keys(M.SECTORS).forEach(function (key) {
      var option = document.createElement("option");
      option.value = key;
      option.textContent = M.SECTORS[key].label;
      sector.appendChild(option);
    });
    var payment = $("pagoHistorico");
    Object.keys(M.PAYMENT_HISTORY).forEach(function (key) {
      var option = document.createElement("option");
      option.value = key;
      option.textContent = M.PAYMENT_HISTORY[key].label;
      payment.appendChild(option);
    });
  }

  function applySelectDefaults() {
    $("sector").value = "servicios_ti";
    $("pagoHistorico").value = "sin_historial";
  }

  // --- Gestión interactiva de lista de Representantes Legales ---
  function getRepList() {
    var raw = String($("representantes").value || "").trim();
    if (!raw) return [];
    return raw.split(/\r?\n/).map(function(s) { return s.trim(); }).filter(Boolean);
  }

  function renderRepList(ruts) {
    var container = $("repListContainer");
    if (!container) return;
    container.innerHTML = "";

    // Si no hay ninguno, mostrar al menos 1 campo vacío para facilitar la entrada
    var list = (ruts && ruts.length) ? ruts : [""];

    list.forEach(function(rutVal, idx) {
      var row = document.createElement("div");
      row.className = "rep-row";

      var badge = document.createElement("span");
      badge.className = "rep-index-badge";
      badge.textContent = "#" + (idx + 1);

      var input = document.createElement("input");
      input.type = "text";
      input.className = "rep-input";
      input.placeholder = "Ej: 12.345.678-9";
      input.value = rutVal;

      input.addEventListener("input", function() {
        syncRepTextarea();
        scheduleSave();
      });

      var btnDel = document.createElement("button");
      btnDel.type = "button";
      btnDel.className = "btn-rep-del";
      btnDel.title = "Eliminar este representante";
      btnDel.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';

      btnDel.addEventListener("click", function() {
        var allRows = container.querySelectorAll(".rep-row");
        if (allRows.length <= 1) {
          // Si es el único, solo limpiar el valor
          input.value = "";
        } else {
          row.remove();
        }
        syncRepTextarea();
        reindexRepBadges();
        scheduleSave();
      });

      row.appendChild(badge);
      row.appendChild(input);
      row.appendChild(btnDel);
      container.appendChild(row);
    });

    syncRepTextarea();
  }

  function reindexRepBadges() {
    var container = $("repListContainer");
    if (!container) return;
    var rows = container.querySelectorAll(".rep-row");
    rows.forEach(function(row, idx) {
      var b = row.querySelector(".rep-index-badge");
      if (b) b.textContent = "#" + (idx + 1);
    });
  }

  function syncRepTextarea() {
    var container = $("repListContainer");
    if (!container) return;
    var inputs = container.querySelectorAll(".rep-input");
    var values = [];
    inputs.forEach(function(inp) {
      var v = inp.value.trim();
      if (v) values.push(v);
    });
    $("representantes").value = values.join("\n");
  }

  function addRepRow(initialValue) {
    var container = $("repListContainer");
    if (!container) return;
    var count = container.querySelectorAll(".rep-row").length;

    var row = document.createElement("div");
    row.className = "rep-row";

    var badge = document.createElement("span");
    badge.className = "rep-index-badge";
    badge.textContent = "#" + (count + 1);

    var input = document.createElement("input");
    input.type = "text";
    input.className = "rep-input";
    input.placeholder = "Ej: 12.345.678-9";
    input.value = initialValue || "";

    input.addEventListener("input", function() {
      syncRepTextarea();
      scheduleSave();
    });

    var btnDel = document.createElement("button");
    btnDel.type = "button";
    btnDel.className = "btn-rep-del";
    btnDel.title = "Eliminar este representante";
    btnDel.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';

    btnDel.addEventListener("click", function() {
      var allRows = container.querySelectorAll(".rep-row");
      if (allRows.length <= 1) {
        input.value = "";
      } else {
        row.remove();
      }
      syncRepTextarea();
      reindexRepBadges();
      scheduleSave();
    });

    row.appendChild(badge);
    row.appendChild(input);
    row.appendChild(btnDel);
    container.appendChild(row);

    input.focus();
    syncRepTextarea();
    scheduleSave();
  }

  if ($("btnAddRep")) {
    $("btnAddRep").addEventListener("click", function() {
      addRepRow("");
    });
  }

  function setForm(data) {
    Object.keys(data).forEach(function (id) {
      var field = $(id);
      if (!field) return;
      if (field.type === "checkbox") field.checked = !!data[id];
      else if (data[id] !== null && data[id] !== undefined) field.value = data[id];
    });
    // Sincronizar UI de lista de representantes si data contiene representantes
    if (data.representantes !== undefined) {
      renderRepList(getRepList());
    }
    updateMoneyHints();
    updateRutValidation();
    updateLiveMetrics();
  }

  function updateMoneyHints() {
    form.querySelectorAll("[data-money]").forEach(function (field) {
      var hint = document.querySelector('[data-hint-for="' + field.id + '"]');
      if (!hint) return;
      var value = Number(field.value);
      hint.textContent = field.value !== "" && Number.isFinite(value) ? M.formatCLP(value) : "";
    });
  }

  function updateRutValidation() {
    ["rut", "rutERut", "rutSolicitante"].forEach(function (id) {
      var field = $(id);
      if (!field) return;
      field.classList.remove("rut-valid", "rut-invalid");

      // Buscar o crear contenedor de feedback
      var fbId = id + "Feedback";
      var fb = $(fbId);
      if (!fb) {
        fb = document.createElement("div");
        fb.id = fbId;
        fb.className = "rut-feedback";
        var labelParent = field.closest("label.field") || field.closest(".field") || field.parentNode;
        if (labelParent) {
          labelParent.appendChild(fb);
        } else if (field.parentNode) {
          field.parentNode.appendChild(fb);
        }
      }

      var raw = String(field.value || "").trim();
      if (raw === "") {
        fb.className = "rut-feedback";
        fb.textContent = "";
        return;
      }

      var clean = M.cleanRut(raw);
      if (clean.length < 2) {
        field.classList.add("rut-invalid");
        fb.className = "rut-feedback show-invalid";
        fb.textContent = "⚠ RUT incompleto (ingresa cuerpo y dígito verificador)";
        return;
      }

      var body = clean.slice(0, -1);
      var dv = clean.slice(-1);
      var sum = 0;
      var multiplier = 2;
      for (var i = body.length - 1; i >= 0; i -= 1) {
        sum += Number(body.charAt(i)) * multiplier;
        multiplier = multiplier === 7 ? 2 : multiplier + 1;
      }
      var res = 11 - (sum % 11);
      var expectedDv = res === 11 ? "0" : res === 10 ? "K" : String(res);

      if (dv === expectedDv) {
        field.classList.add("rut-valid");
        fb.className = "rut-feedback show-valid";
        fb.textContent = "✓ RUT válido (Módulo 11)";
      } else {
        field.classList.add("rut-invalid");
        fb.className = "rut-feedback show-invalid";
        fb.textContent = "✕ RUT inválido (Módulo 11): para " + body + " el dígito verificador debe ser -" + expectedDv + " y no -" + dv;
      }
    });

    // Validar también inputs dinámicos de representantes legales
    var repContainer = $("repListContainer");
    if (repContainer) {
      repContainer.querySelectorAll(".rep-row").forEach(function(row) {
        var inp = row.querySelector(".rep-input");
        if (!inp) return;
        row.classList.remove("rut-row-valid", "rut-row-invalid");
        var val = String(inp.value || "").trim();
        if (!val) return;
        if (M.isValidRut(M.cleanRut(val))) {
          row.classList.add("rut-row-valid");
        } else {
          row.classList.add("rut-row-invalid");
        }
      });
    }
  }

  function setText(id, text) {
    var element = $(id);
    if (element) element.textContent = text;
  }

  function ratioText(value) {
    if (value === null || value === undefined) return "—";
    if (value >= 999) return "∞";
    return M.formatRatio(value) + "x";
  }

  function updateLiveMetrics() {
    var input = M.normalize(toModelInput(collectForm()));
    var r = M.ratios(input);
    setText("liveRc", ratioText(r.razonCorriente));
    setText("liveAcid", ratioText(r.pruebaAcida));
    setText("liveLeverage", ratioText(r.deudaPatrimonio));
    setText("liveNetDebt", r.deudaNetaEbitda === -1 ? "Caja neta" : ratioText(r.deudaNetaEbitda));
    setText("liveMargin", M.formatPct(r.margenEbitda));
    setText("liveFreeCash", r.flujoLibre === null ? "—" : M.formatCLP(r.flujoLibre));
    setText("liveDso", r.dso === null ? "—" : Math.round(r.dso) + " días");
  }

  function processPdfUpload(field, fileOrFiles) {
    var docType = field.getAttribute("data-extract-type") || "auto";
    var formData = new FormData();
    var isMultiple = Array.isArray(fileOrFiles);
    var filesList = isMultiple ? fileOrFiles : [fileOrFiles];

    for (var fi = 0; fi < filesList.length; fi++) {
      formData.append("file", filesList[fi]);
    }
    formData.append("type", docType);

    var dpBox = $("docProgressBox");
    var dpText = $("docProgressText");
    var dpBar = $("docProgressBar");
    var dpPct = $("docProgressPct");
    var dpTimer = null;

    var displayName = isMultiple ? (filesList.length + " balances comparativos") : filesList[0].name;

    if (dpBox) {
      dpBox.classList.remove("hidden");
      var step = 20;
      dpText.textContent = "Cargando y leyendo " + displayName + "...";
      dpBar.style.width = "20%";
      dpPct.textContent = "20%";

      dpTimer = setInterval(function() {
        if (step < 88) {
          step += Math.floor(Math.random() * 15) + 6;
          if (step > 88) step = 88;
          dpBar.style.width = step + "%";
          dpPct.textContent = step + "%";
          if (step > 45 && step <= 70) {
            dpText.textContent = "Extrayendo partidas financieras y formularios...";
          } else if (step > 70) {
            dpText.textContent = "Consolidando métricas del negocio...";
          }
        }
      }, 500);
    }

    showToast("Extrayendo datos de " + displayName + "...");
    fetch(API_BASE + "/api/extract-pdf", {
      method: "POST",
      body: formData
    })
    .then(function(res) { return res.json(); })
    .then(function(res) {
      clearInterval(dpTimer);
      if (dpBar) dpBar.style.width = "100%";
      if (dpPct) dpPct.textContent = "100%";
      if (dpText) dpText.textContent = "Extracción completada: " + displayName;
      setTimeout(function() {
        if (dpBox) dpBox.classList.add("hidden");
      }, 1500);

      if (!res.success || !res.data) {
        showToast(res.error || "No se pudo extraer información del archivo");
        return;
      }
      var d = res.data;
      var okCheck = document.querySelector("#" + field.id + "Ok");
      if (okCheck) okCheck.checked = true;

      if (docType === "erut" || d.tipo === "e-RUT") {
        if (d.rut) {
          $("rut").value = d.rut;
          $("rutERut").value = d.rut;
        }
        if (d.razon_social) $("razonSocial").value = d.razon_social;
        if (d.solicitante_rut) $("rutSolicitante").value = d.solicitante_rut;
        showToast("e-RUT procesado: " + (d.razon_social || d.rut));
      } else if (docType === "cmf" || d.tipo === "CMF_DEUDAS") {
        if (d.deuda_total !== undefined && $("deudaFinanciera")) {
          $("deudaFinanciera").value = d.deuda_total;
          $("deudaFinanciera").dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (d.instituciones !== undefined && $("instituciones")) {
          $("instituciones").value = d.instituciones;
          $("instituciones").dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (d.max_dias_mora !== undefined && $("maxDiasMora")) {
          $("maxDiasMora").value = d.max_dias_mora;
          $("maxDiasMora").dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (d.deuda_vencida !== undefined && $("deudaVencida")) {
          $("deudaVencida").value = d.deuda_vencida;
          $("deudaVencida").dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (d.deuda_castigada !== undefined && d.deuda_castigada > 0 && $("deudaCastigada")) {
          $("deudaCastigada").value = d.deuda_castigada;
          $("deudaCastigada").dispatchEvent(new Event("input", { bubbles: true }));
        }
        // La mora CMF (financiera) ya se refleja en maxDiasMora y deudaVencida.
        // NO se carga en morosidades/montoMorosidades (campos DICOM/comerciales):
        // provocaría triple conteo en la dimensión Pago y borrado de datos DICOM reales.
        var instText = d.instituciones ? " (" + d.instituciones + " acreedores)" : "";
        showToast("CMF procesado: Deuda " + M.formatCLP(d.deuda_total) + instText + ", Mora: " + (d.max_dias_mora || 0) + " días");
      } else if (docType === "carpeta_tributaria" || d.tipo === "CARPETA_TRIBUTARIA") {
        var fieldsToUpdate = {};
        if (d.rut) fieldsToUpdate.rut = d.rut;
        if (d.razon_social) fieldsToUpdate.razonSocial = d.razon_social;
        if (d.antiguedad_anios) fieldsToUpdate.antiguedad = d.antiguedad_anios;
        if (d.ventas_12m) fieldsToUpdate.ventas12m = d.ventas_12m;
        if (d.tendencia_ventas) fieldsToUpdate.tendenciaVentas = d.tendencia_ventas;
        if (d.eeff_f22) {
          // El Formulario 22 (código 122) informa 'Total del Activo', no 'Activo Corriente'.
          // No se asigna a activoCorriente para no distorsionar la razón corriente ni la liquidez.
          if (d.eeff_f22.total_pasivo) fieldsToUpdate.pasivoTotal = d.eeff_f22.total_pasivo;
          if (d.eeff_f22.patrimonio) fieldsToUpdate.patrimonio = d.eeff_f22.patrimonio;
          if (d.eeff_f22.caja) fieldsToUpdate.caja = d.eeff_f22.caja;
          if (d.eeff_f22.inventarios) fieldsToUpdate.inventarios = d.eeff_f22.inventarios;
          // 'resultado' del F22 es utilidad neta del ejercicio, NO EBITDA:
          // no se asigna a ebitda para no corruptir el cálculo (incluye GF, depreciación e impuestos).
        }

        // Detectar si alguno de los campos de destino ya tiene datos ingresados
        var hasExistingData = Object.keys(fieldsToUpdate).some(function (fieldId) {
          var el = $(fieldId);
          return el && String(el.value || "").trim() !== "";
        });

        var shouldApply = true;
        if (hasExistingData) {
          shouldApply = window.confirm(
            "La Carpeta Tributaria contiene datos de ventas y balances F22 (Caja, Inventarios, Pasivo Total, Patrimonio) que actualizarán el formulario.\n\n¿Deseas aplicar los datos oficiales extraídos?"
          );
        }

        if (shouldApply) {
          Object.keys(fieldsToUpdate).forEach(function (fieldId) {
            var el = $(fieldId);
            if (el) {
              el.value = fieldsToUpdate[fieldId];
              el.dispatchEvent(new Event("input", { bubbles: true }));
            }
          });
          showToast("Carpeta Tributaria procesada: Ventas 12m " + M.formatCLP(d.ventas_12m) + (d.eeff_f22 ? " + Balances F22" : "") + (d.eeff_f22 && d.eeff_f22.resultado ? " · Resultado neto F22: " + M.formatCLP(d.eeff_f22.resultado) + " (no asignado a EBITDA)" : ""));
        } else {
          showToast("Extracción completada: Se mantuvieron los datos existentes.");
        }
      } else if (docType === "estatutos" || d.tipo === "ESTATUTOS_PODERES") {
        if (d.ruts_detectados && d.ruts_detectados.length) {
          var existingReps = String($("representantes").value || "").trim();
          var applyReps = true;
          if (existingReps !== "") {
            applyReps = window.confirm("Ya existen representantes ingresados. ¿Deseas reemplazarlos por los detectados en los estatutos?");
          }
          if (applyReps) {
            $("representantes").value = d.ruts_detectados.join("\n");
            renderRepList(d.ruts_detectados);
          }
        }
        if (d.facultades_financieras_detectadas) {
          $("facultades").checked = true;
        }
        $("sociedadVigente").checked = true;
        showToast("Estatutos/Poderes procesados correctamente");
      } else if (docType === "eeff" || d.tipo === "ESTADOS_FINANCIEROS") {
        var eeffFields = {};
        if (d.activoCorriente !== null && d.activoCorriente !== undefined) eeffFields.activoCorriente = d.activoCorriente;
        if (d.pasivoCorriente !== null && d.pasivoCorriente !== undefined) eeffFields.pasivoCorriente = d.pasivoCorriente;
        if (d.cuentasPorCobrar !== null && d.cuentasPorCobrar !== undefined) eeffFields.cuentasPorCobrar = d.cuentasPorCobrar;
        if (d.inventarios !== null && d.inventarios !== undefined) eeffFields.inventarios = d.inventarios;
        if (d.caja !== null && d.caja !== undefined) eeffFields.caja = d.caja;
        if (d.pasivoTotal !== null && d.pasivoTotal !== undefined) eeffFields.pasivoTotal = d.pasivoTotal;
        if (d.patrimonio !== null && d.patrimonio !== undefined) eeffFields.patrimonio = d.patrimonio;
        if (d.ebitda !== null && d.ebitda !== undefined) eeffFields.ebitda = d.ebitda;
        if (d.flujoCajaOperacional !== null && d.flujoCajaOperacional !== undefined) eeffFields.flujoCajaOperacional = d.flujoCajaOperacional;
        if (d.gastosFinancieros !== null && d.gastosFinancieros !== undefined) eeffFields.gastosFinancieros = d.gastosFinancieros;
        if (d.servicioDeuda !== null && d.servicioDeuda !== undefined) eeffFields.servicioDeuda = d.servicioDeuda;
        if (d.deudaFinanciera !== null && d.deudaFinanciera !== undefined) eeffFields.deudaFinanciera = d.deudaFinanciera;
        if (d.deudaFinancieraCP !== null && d.deudaFinancieraCP !== undefined) eeffFields.deudaFinancieraCP = d.deudaFinancieraCP;
        if (d.deudaSociosRelacionados !== null && d.deudaSociosRelacionados !== undefined) extractedExtra.deudaSociosRelacionados = d.deudaSociosRelacionados;
        if (d.diferenciaCambio !== null && d.diferenciaCambio !== undefined) extractedExtra.diferenciaCambio = d.diferenciaCambio;

        var hasExistingEeff = Object.keys(eeffFields).some(function (fieldId) {
          var el = $(fieldId);
          return el && String(el.value || "").trim() !== "";
        });

        var applyEeff = true;
        if (hasExistingEeff) {
          applyEeff = window.confirm(
            "Se extrajeron partidas contables del Balance / Estados Financieros (Pasivo Cte, Cuentas por Cobrar, Gastos Financieros, Servicio de Deuda).\n\n¿Deseas completar o actualizar los campos del Paso 3 con estos valores?"
          );
        }

        if (applyEeff) {
          var updatedCount = 0;
          Object.keys(eeffFields).forEach(function (fieldId) {
            var el = $(fieldId);
            if (el) {
              el.value = eeffFields[fieldId];
              el.dispatchEvent(new Event("input", { bubbles: true }));
              updatedCount += 1;
            }
          });
          if ($("eeccVerificados")) $("eeccVerificados").checked = true;
          var extraMsg = (d.desglose_flujo && d.desglose_flujo.metodo === "COMPARATIVO_DOS_PERIODOS") ? " (Flujo de caja comparativo calculado)" : "";
          if (d.diferenciaCambio !== null && d.diferenciaCambio !== undefined && d.diferenciaCambio !== 0) {
            extraMsg += " · Dif. cambio neta: " + M.formatCLP(d.diferenciaCambio) + " (no incluida en Gastos Financieros)";
          }
          showToast("Balance procesado: " + updatedCount + " partidas asignadas" + extraMsg);
        }
      }

      updateMoneyHints();
      updateRutValidation();
      updateLiveMetrics();
      scheduleSave();
    })
    .catch(function(err) {
      clearInterval(dpTimer);
      if (dpBox) dpBox.classList.add("hidden");
      showToast("Error de conexión al procesar el PDF");
    });
  }

  function bindFileLabels() {
    form.querySelectorAll('input[type="file"]').forEach(function (field) {
      field.addEventListener("change", function () {
        var label = document.querySelector('[data-file-label="' + field.id + '"]');
        if (!label) return;
        if (!field.files || field.files.length === 0) {
          label.textContent = "Sin archivo";
          return;
        }
        var names = Array.prototype.map.call(field.files, function (file) { return file.name; });
        label.textContent = (field.files.length > 1 ? field.files.length + " archivos: " : "") + names.join(", ");

        var pdfFiles = Array.prototype.filter.call(field.files, function (file) {
          return file.name.toLowerCase().endsWith(".pdf");
        });
        if (pdfFiles.length > 0) {
          processPdfUpload(field, pdfFiles.length === 1 ? pdfFiles[0] : pdfFiles);
        }
      });
    });
  }

  function saveDraft() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        version: 1,
        savedAt: new Date().toISOString(),
        data: collectForm()
      }));
    } catch (error) {
      return;
    }
  }

  function scheduleSave() {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(saveDraft, 400);
  }

  function clearDraft() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      return;
    }
  }

  function loadDraft() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return;
      var draft = JSON.parse(stored);
      if (!draft || draft.version !== 1 || !draft.data) return;
      setForm(draft.data);
      if (draftNotice && draftText) {
        draftText.textContent = "Borrador restaurado (" + new Date(draft.savedAt).toLocaleString("es-CL") + ").";
        draftNotice.classList.remove("hidden");
      }
    } catch (error) {
      return;
    }
  }

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toast.classList.remove("show");
    }, 2600);
  }

  function clearResults() {
    LAST_RESULT = null;
    if (results) {
      results.innerHTML = "";
      results.classList.add("hidden");
    }
    if (btnPrint) btnPrint.disabled = true;
  }

  function markStale() {
    if (!LAST_RESULT || results.classList.contains("hidden")) return;
    if (btnPrint) btnPrint.disabled = true;
    results.querySelectorAll("[data-print], [data-copy]").forEach(function (button) {
      button.disabled = true;
    });
    if (results.querySelector(".stale-notice")) return;
    var notice = document.createElement("div");
    notice.className = "notice stale-notice";
    notice.innerHTML = "Los datos del formulario cambiaron. Vuelve a evaluar antes de usar o imprimir el resultado. " +
      '<button class="btn ghost small" type="button" data-reevaluate>Volver a evaluar</button>';
    results.insertBefore(notice, results.firstChild);
    notice.querySelector("[data-reevaluate]").addEventListener("click", runEvaluation);
  }

  function resetFileLabels() {
    form.querySelectorAll('input[type="file"]').forEach(function (field) {
      var label = document.querySelector('[data-file-label="' + field.id + '"]');
      if (label) label.textContent = "Sin archivo";
    });
  }

  function resetForm() {
    form.reset();
    applySelectDefaults();
    clearDraft();
    clearResults();
    resetFileLabels();
    if (draftNotice) draftNotice.classList.add("hidden");
    updateMoneyHints();
    updateLiveMetrics();
  }

  function loadExample(profileKey) {
    var key = profileKey;
    if (!key) {
      var sel = $("selectExampleProfile");
      key = (sel && sel.value) ? sel.value : "aprobado";
    }
    var selectedProfile = EXAMPLE_PROFILES[key] || EXAMPLE_PROFILES.aprobado;

    form.reset();
    setForm(selectedProfile);
    clearResults();
    resetFileLabels();

    // Abrir las cards para que el usuario pueda ver los datos cargados en cada paso
    document.querySelectorAll("#creditForm details.card").forEach(function(card) {
      card.open = true;
    });

    if (draftNotice) draftNotice.classList.add("hidden");
    saveDraft();
    showToast("Ejemplo cargado (" + selectedProfile.razonSocial + "). Presiona 'Evaluar crédito' para ver los resultados.");
  }

  function metric(label, value, hint) {
    return '<div class="metric"><small>' + esc(label) + "</small><b>" + esc(value) + "</b>" +
      (hint ? "<span>" + esc(hint) + "</span>" : "") + "</div>";
  }

  function formatPoints(value) {
    return M.formatRatio(value, 2);
  }

  function limitingLabel(key) {
    var labels = {
      commercial: "límite comercial",
      financial: "límite financiero",
      risk: "política de riesgo por cliente",
      policy: "política de crédito"
    };
    return labels[key] || "—";
  }

  function statusNote(r) {
    if (r.status.key === "pending") return "El puntaje es provisional. Completa los antecedentes pendientes para habilitar una decisión.";
    if (r.status.key === "blocked") return "El puntaje no prevalece sobre los bloqueos críticos. Resuelve los bloqueos antes de continuar.";
    if (r.status.key === "no_availability") return "El límite bruto ya está consumido por la exposición actual. No hay disponibilidad adicional.";
    if (r.status.key === "no_ordinary" || r.status.key === "rejected") return "No se recomienda otorgar crédito ordinario con los antecedentes actuales.";
    if (r.status.key === "review") return "Se requiere revisión de jefatura, mitigantes o una reducción del límite antes de aprobar.";
    return "Decisión sujeta a revisión humana y validación legal del plazo.";
  }

  function issueGroup(title, items, className, markCritical) {
    if (!items.length) return "";
    return '<div class="issue-group"><h3>' + esc(title) + '</h3><ul class="issue-list ' + className + '">' +
      items.map(function (item) {
        return "<li>" + (markCritical && item.critical ? "<strong>Crítico: </strong>" : "") + esc(item.text) + "</li>";
      }).join("") + "</ul></div>";
  }

  function renderIssues(r) {
    var parts = [];
    parts.push(issueGroup("Bloqueos críticos", r.hardBlockers, "hard", false));
    parts.push(issueGroup("Antecedentes pendientes", r.pendingItems, "pending", false));
    parts.push(issueGroup("Alertas de riesgo", r.warnings, "warning", true));
    parts.push(issueGroup("Observaciones", r.infoItems, "info", false));
    if (!r.hardBlockers.length && !r.pendingItems.length && !r.warnings.length && !r.infoItems.length) {
      parts.push('<div class="issue-group"><ul class="issue-list ok"><li>Sin alertas críticas.</li></ul></div>');
    }
    return parts.join("");
  }

  function controlRow(label, ok, detail, optional) {
    var status = optional && !ok ? "Opcional" : ok ? "OK" : "Revisar";
    var color = optional && !ok ? "var(--mut)" : ok ? "var(--ok)" : "var(--warn)";
    return "<tr><td>" + esc(label) + '</td><td><span class="score-chip" style="color:' + color + '">' +
      esc(status) + "</span></td><td>" + esc(detail || "—") + "</td></tr>";
  }

  function renderControls(r) {
    var docsOk = REQUIRED_DOCS.filter(function (key) { return r.input.docs[key]; }).length;
    var rows = [
      controlRow("RUT de la empresa", M.isValidRut(r.input.rut), M.formatRut(r.input.rut)),
      controlRow("RUT del e-RUT coincide", !!r.input.rutERut && r.input.rutERut === r.input.rut, M.formatRut(r.input.rutERut)),
      controlRow("RUT del solicitante", M.isValidRut(r.input.rutSolicitante), M.formatRut(r.input.rutSolicitante)),
      controlRow("Solicitante en nómina de representantes", r.input.representantes.indexOf(r.input.rutSolicitante) >= 0, r.input.representantes.length + " representante(s) informado(s)"),
      controlRow("Inicio de actividades vigente", r.input.inicioVigente, ""),
      controlRow("Sociedad vigente", r.input.sociedadVigente, ""),
      controlRow("Facultades del representante", r.input.facultades, ""),
      controlRow("Documentos obligatorios", docsOk === REQUIRED_DOCS.length, docsOk + "/" + REQUIRED_DOCS.length + " revisados"),
      controlRow("Estados financieros verificados", r.input.eeccVerificados, ""),
      controlRow("DICOM revisado", r.input.docs.dicom, r.input.docs.dicom ? "Presentado" : "No presentado", true)
    ];
    return '<div class="table-wrap"><table><thead><tr><th>Control</th><th>Estado</th><th>Detalle</th></tr></thead><tbody>' +
      rows.join("") + "</tbody></table></div>";
  }

  function renderDimensions(r) {
    return r.dimensions.map(function (dimension) {
      var color = dimension.note >= 70 ? "var(--ok)" : dimension.note >= 55 ? "var(--ac)" : dimension.note >= 40 ? "var(--warn)" : "var(--bad)";
      var rows = dimension.indicators.map(function (indicator) {
        return '<li><span class="name">' + esc(indicator.label) + '</span><span class="value">' +
          esc(indicator.display) + '</span><span class="pts' + (indicator.score < 50 ? " underperform" : "") + '">' +
          indicator.score + "</span></li>";
      }).join("");
      return '<div class="dimension">' +
        '<div class="dim-head"><div><strong>' + esc(dimension.label) + "</strong><small>Peso " +
        dimension.weight + "% · Contribución " + formatPoints(dimension.contribution) + ' pts</small></div>' +
        '<span class="score-chip">' + dimension.note + "/100</span></div>" +
        '<div class="bar"><span style="width:' + dimension.note + "%;background:" + color + '"></span></div>' +
        '<ul class="indicator-list">' + rows + "</ul></div>";
    }).join("") +
      '<div class="dimension" style="background:var(--ac-soft)"><div class="dim-head"><div><strong>Puntaje total</strong><small>Suma ponderada de las cinco dimensiones</small></div><span class="score-chip">' +
      M.formatRatio(r.score, 1) + "/100</span></div></div>";
  }

  function renderLimits(r) {
    var approvable = ["approved", "conditional", "review", "no_availability"].indexOf(r.status.key) >= 0;
    if (!approvable) {
      return '<section class="result-section"><h2>Cálculo del límite</h2><p class="small muted">' +
        (r.status.key === "pending"
          ? "El límite no se habilita hasta completar los antecedentes pendientes."
          : "No se calcula línea ordinaria para esta decisión.") + "</p></section>";
    }
    var preAdjustment = Math.min(r.limits.commercial, r.limits.financial, r.limits.risk);
    var adjustment = Math.max(0, preAdjustment - r.limits.gross);
    var eeffHaircutRow = r.limits.isEeffPenalized
      ? '<tr><td><span style="color:var(--warn);font-weight:600;">⚠ Castigo por falta de EE.FF./Balance (-50%)</span><span class="formula">Restricción por evaluación exclusiva sobre flujo SII (F29)</span></td><td class="num" style="color:var(--warn);font-weight:600;">-' + M.formatCLP(preAdjustment * 0.5) + "</td></tr>"
      : "";
    var adjustmentRow = adjustment > 0 && !r.limits.isEeffPenalized
      ? '<tr><td>Ajuste por revisión de riesgo</td><td class="num">-' + M.formatCLP(adjustment) + "</td></tr>"
      : "";
    var financialFormula = r.limits.isEeffPenalized
      ? '(Venta mensual F29 × 50%) × ' + esc(r.limits.factor)
      : 'máx(0, FCO − servicio de deuda) × ' + esc(r.limits.multiplier);
    return '<section class="result-section"><h2>Cálculo del límite</h2><div class="table-wrap compact"><table>' +
      '<thead><tr><th>Concepto</th><th class="num">Valor</th></tr></thead><tbody>' +
      '<tr><td>Límite comercial<span class="formula">(Ventas 12m / 365) × ' + (r.limits.termDays || 0) + " días × " + esc(r.limits.factor) + "</span></td><td class=\"num\">" + M.formatCLP(r.limits.commercial) + "</td></tr>" +
      '<tr><td>Límite financiero<span class="formula">' + financialFormula + "</span></td><td class=\"num\">" + M.formatCLP(r.limits.financial) + "</td></tr>" +
      '<tr><td>Límite de política de riesgo' + (r.limits.isRiskEstimated ? '<span class="formula">Estimado dinámico (Solvencia/Ventas y Scoring)</span>' : '<span class="formula">Parámetro fijado por analista</span>') + '</td><td class="num">' + M.formatCLP(r.limits.risk) + "</td></tr>" +
      eeffHaircutRow +
      adjustmentRow +
      '<tr><td><b>Límite bruto</b><span class="formula">' + (r.limits.isEeffPenalized ? 'Menor de límites con castigo 50%' : 'Menor de los límites aplicables') + '</span></td><td class="num"><b>' + M.formatCLP(r.limits.gross) + "</b></td></tr>" +
      '<tr><td>Exposición actual</td><td class="num">' + M.formatCLP(r.limits.exposure) + "</td></tr>" +
      '<tr><td>Disponible adicional</td><td class="num">' + M.formatCLP(r.limits.available) + "</td></tr>" +
      '<tr><td>Monto solicitado</td><td class="num">' + M.formatCLP(r.limits.requested) + "</td></tr>" +
      '<tr class="total"><td>Monto aprobado</td><td class="num">' + M.formatCLP(r.limits.approved) + "</td></tr>" +
      "</tbody></table></div><p class=\"small muted\" style=\"margin:8px 0 0\">Factor limitante: " +
      esc(limitingLabel(r.limits.limitingFactor)) + (r.limits.isEeffPenalized ? ". <b>Aviso:</b> Límite reducido en un 50% por falta de balance contable." : "") + ". El monto aprobado se redondea a $100.000 y nunca supera la disponibilidad.</p></section>";
  }

  function renderTerm(r) {
    var mitigants = [];
    if (r.input.aval) mitigants.push("Aval personal o solidario");
    if (r.input.garantia) mitigants.push("Garantía real o prenda");
    if (r.input.seguroCredito) mitigants.push("Seguro de crédito comercial");
    var notes = r.term.notes.slice();
    if (r.term.approved > 30) notes.push("Plazo superior a 30 días: validación legal registrada por el analista.");
    if (r.term.approved === 90) notes.push("Excepción de 90 días: requiere autorización superior y justificación comercial documentada.");
    return '<section class="result-section"><h2>Plazo y condiciones</h2><div class="metrics">' +
      metric("Plazo solicitado", r.term.requested ? r.term.requested + " días" : "—", "") +
      metric("Plazo máximo interno", r.term.max ? r.term.max + " días" : "—", "") +
      metric("Plazo aprobado", r.term.approved ? r.term.approved + " días" : "—", "") +
      "</div>" +
      (mitigants.length ? '<p class="small" style="margin:12px 0 0"><b>Mitigantes registrados:</b> ' + esc(mitigants.join(", ")) + "</p>" : "") +
      (notes.length ? '<ul class="conditions">' + notes.map(function (note) { return "<li>" + esc(note) + "</li>"; }).join("") + "</ul>" : "") +
      '<p class="legal" style="margin-top:12px">Ley N.º 19.983, modificada por la Ley N.º 21.131: regla general de pago de facturas dentro de 30 días corridos desde su recepción. Los plazos superiores requieren cumplir las condiciones legales, incluyendo acuerdo escrito e inscripción cuando proceda. La evaluación crediticia no sustituye la validación jurídica.</p></section>';
  }

  var FEEDBACK_KEY = "credit-ml-feedback-v1";
  function loadFeedback() {
    try { return JSON.parse(localStorage.getItem(FEEDBACK_KEY) || "[]"); } catch (e) { return []; }
  }
  function saveFeedback(list) {
    try { localStorage.setItem(FEEDBACK_KEY, JSON.stringify(list)); } catch (e) {}
  }
  function renderPrediction(r) {
    var p = r.prediction;
    if (!p) return '<p class="small muted">Modelo predictivo no disponible.</p>';
    var conf = (p.confidence * 100).toFixed(1) + "%";
    var review = p.needsReview ? "Si (revision humana requerida)" : "No";
    var probRows = Object.keys(p.probabilities).map(function (k) {
      return "<tr><td>" + esc(k) + "</td><td class=\"num\">" + (p.probabilities[k] * 100).toFixed(1) + "%</td></tr>";
    }).join("");
    return '<div class="metrics">' +
      metric("Decision predicha", p.label, "Modelo supervisado") +
      metric("Confianza", conf, "Probabilidad de la clase") +
      metric("Revision humana", review, "Umbral 75% o clases de riesgo") +
      '</div>' +
      '<div class="table-wrap compact" style="margin-top:10px"><table><thead><tr><th>Clase</th><th class="num">Probabilidad</th></tr></thead><tbody>' + probRows + '</tbody></table></div>' +
      '<div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">' +
      '<button class="btn ghost small" type="button" data-ml-feedback="approved">Marcar aprobado</button>' +
      '<button class="btn ghost small" type="button" data-ml-feedback="rejected">Marcar rechazado</button>' +
      '<button class="btn ghost small" type="button" data-ml-feedback="review">Marcar revision</button>' +
      '<button class="btn ghost small" type="button" data-ml-train>Entrenar con feedback (' + loadFeedback().length + ')</button>' +
      '<button class="btn ghost small" type="button" data-ml-reset>Reiniciar modelo</button>' +
      '</div>' +
      '<p class="small muted" style="margin-top:8px">El feedback humano se guarda localmente y permite reentrenar el modelo (aprendizaje supervisado). La decision final sigue siendo humana.</p>';
  }

  function renderResults(r) {
    LAST_RESULT = r;
    var score = Math.max(0, Math.min(100, r.scoreDisplay));
    var company = esc(r.input.razonSocial || "Empresa sin nombre");
    var rut = r.input.rut ? " · " + esc(M.formatRut(r.input.rut)) : "";
    var generated = new Date(r.generatedAt).toLocaleString("es-CL");
    var analyst = esc(r.input.analista || "No informado");
    var observations = r.input.observaciones
      ? '<p class="small muted" style="margin:8px 0 0"><b>Observaciones:</b> ' + esc(r.input.observaciones) + "</p>"
      : "";
    var isPending = r.status.key === "pending";
    var approvedValue = isPending ? "Pendiente" : M.formatCLP(r.limits.approved);
    var grossValue = isPending ? "—" : M.formatCLP(r.limits.gross);
    var availableValue = isPending ? "—" : M.formatCLP(r.limits.available);
    var termValue = r.term.approved ? r.term.approved + " días" : "—";
    var classificationText = r.classification.label;
    var scoreHint = r.classification.label;
    if (r.status.key === "blocked") classificationText += " · bloqueado por alertas";
    else if (r.status.key === "pending") {
      classificationText = "Puntaje provisional";
      scoreHint = "Faltan antecedentes";
    } else if (r.status.key === "review" && r.score >= 85) {
      classificationText += " · sujeto a revisión";
    }
    function renderKpiCards(r) {
      var ratios = r.ratios;
      
      // 1. Razón Corriente (Benchmark: >= 1.3x)
      var rcVal = ratios.razonCorriente;
      var rcClass = rcVal === null ? "kpi-info" : rcVal >= 1.3 ? "kpi-success" : rcVal >= 1.0 ? "kpi-warning" : "kpi-danger";
      var rcBadge = rcVal === null ? '<span class="kpi-badge badge-neutral">S/D</span>' : rcVal >= 1.3 ? '<span class="kpi-badge badge-ok">Saludable</span>' : rcVal >= 1.0 ? '<span class="kpi-badge badge-warn">Ajustado</span>' : '<span class="kpi-badge badge-bad">Riesgo</span>';
      var rcText = rcVal === null ? "—" : (rcVal >= 999 ? "∞" : M.formatRatio(rcVal) + "x");
      var rcPct = rcVal === null ? 0 : Math.min(100, Math.round((rcVal / 2.0) * 100));

      // 2. Cobertura de Deuda Neta / EBITDA (Benchmark: <= 2.5x)
      var netDebtVal = ratios.deudaNetaEbitda;
      var netDebtClass = netDebtVal === null ? "kpi-info" : (netDebtVal === -1 || netDebtVal <= 2.5) ? "kpi-success" : netDebtVal <= 3.5 ? "kpi-warning" : "kpi-danger";
      var netDebtBadge = netDebtVal === null ? '<span class="kpi-badge badge-neutral">S/D</span>' : netDebtVal === -1 ? '<span class="kpi-badge badge-ok">Caja Neta</span>' : netDebtVal <= 2.5 ? '<span class="kpi-badge badge-ok">Óptimo</span>' : netDebtVal <= 3.5 ? '<span class="kpi-badge badge-warn">Moderado</span>' : '<span class="kpi-badge badge-bad">Elevado</span>';
      var netDebtText = netDebtVal === null ? "—" : netDebtVal === -1 ? "Caja neta" : (netDebtVal >= 999 ? "Excesiva" : M.formatRatio(netDebtVal) + "x");
      var netDebtPct = netDebtVal === null ? 0 : netDebtVal === -1 ? 100 : Math.min(100, Math.max(10, Math.round((4.0 - Math.min(4.0, netDebtVal)) / 4.0 * 100)));

      // 3. Margen EBITDA (Rentabilidad Operativa)
      var mEbitda = ratios.margenEbitda;
      var ebitdaClass = mEbitda === null ? "kpi-info" : mEbitda >= 0.12 ? "kpi-success" : mEbitda >= 0.05 ? "kpi-warning" : "kpi-danger";
      var ebitdaBadge = mEbitda === null ? '<span class="kpi-badge badge-neutral">S/D</span>' : mEbitda >= 0.12 ? '<span class="kpi-badge badge-ok">Sólido</span>' : mEbitda >= 0.05 ? '<span class="kpi-badge badge-warn">Marginal</span>' : '<span class="kpi-badge badge-bad">Crítico</span>';
      var ebitdaText = mEbitda === null ? "—" : M.formatPct(mEbitda);
      var ebitdaPct = mEbitda === null ? 0 : Math.min(100, Math.max(5, Math.round((mEbitda / 0.25) * 100)));

      // 4. DSO - Días de Rotación de Cartera (Ley 19.983: <= 30-45 días)
      var dsoVal = ratios.dso;
      var dsoClass = dsoVal === null ? "kpi-info" : dsoVal <= 45 ? "kpi-success" : dsoVal <= 75 ? "kpi-warning" : "kpi-danger";
      var dsoBadge = dsoVal === null ? '<span class="kpi-badge badge-neutral">S/D</span>' : dsoVal <= 45 ? '<span class="kpi-badge badge-ok">Rápido</span>' : dsoVal <= 75 ? '<span class="kpi-badge badge-warn">Normal</span>' : '<span class="kpi-badge badge-bad">Lento</span>';
      var dsoText = dsoVal === null ? "—" : Math.round(dsoVal) + " días";
      var dsoPct = dsoVal === null ? 0 : Math.min(100, Math.max(10, Math.round((120 - Math.min(120, dsoVal)) / 120 * 100)));

      // 5. Apalancamiento Financiero (Pasivo / Patrimonio)
      var levVal = ratios.deudaPatrimonio;
      var levClass = levVal === null ? "kpi-info" : levVal <= 1.5 ? "kpi-success" : levVal <= 2.5 ? "kpi-warning" : "kpi-danger";
      var levBadge = levVal === null ? '<span class="kpi-badge badge-neutral">S/D</span>' : levVal <= 1.5 ? '<span class="kpi-badge badge-ok">Bajo</span>' : levVal <= 2.5 ? '<span class="kpi-badge badge-warn">Medio</span>' : '<span class="kpi-badge badge-bad">Alto</span>';
      var levText = levVal === null ? "—" : (levVal >= 999 ? "Negativo / Inf" : M.formatRatio(levVal) + "x");
      var levPct = levVal === null ? 0 : Math.min(100, Math.max(10, Math.round((3.0 - Math.min(3.0, levVal)) / 3.0 * 100)));

      // 6. Flujo Libre Operacional
      var fLibre = ratios.flujoLibre;
      var fClass = fLibre === null ? "kpi-info" : fLibre > 0 ? "kpi-success" : "kpi-danger";
      var fBadge = fLibre === null ? '<span class="kpi-badge badge-neutral">S/D</span>' : fLibre > 0 ? '<span class="kpi-badge badge-ok">Superávit</span>' : '<span class="kpi-badge badge-bad">Déficit</span>';
      var fText = fLibre === null ? "—" : M.formatCLP(fLibre);

      return '<div class="kpi-grid">' +
        // Card 1
        '<div class="kpi-card ' + rcClass + '">' +
          '<div class="kpi-header"><span class="kpi-title">Razón Corriente</span>' + rcBadge + '</div>' +
          '<div class="kpi-value">' + rcText + '</div>' +
          '<div class="kpi-subtitle">Activo / Pasivo Cte (Meta: &ge; 1.3x)</div>' +
          '<div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:' + rcPct + '%;"></div></div>' +
        '</div>' +
        // Card 2
        '<div class="kpi-card ' + netDebtClass + '">' +
          '<div class="kpi-header"><span class="kpi-title">Deuda Neta / EBITDA</span>' + netDebtBadge + '</div>' +
          '<div class="kpi-value">' + netDebtText + '</div>' +
          '<div class="kpi-subtitle">Capacidad de repago (Meta: &le; 2.5x)</div>' +
          '<div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:' + netDebtPct + '%;"></div></div>' +
        '</div>' +
        // Card 3
        '<div class="kpi-card ' + ebitdaClass + '">' +
          '<div class="kpi-header"><span class="kpi-title">Margen EBITDA</span>' + ebitdaBadge + '</div>' +
          '<div class="kpi-value">' + ebitdaText + '</div>' +
          '<div class="kpi-subtitle">Generación operacional sobre ventas</div>' +
          '<div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:' + ebitdaPct + '%;"></div></div>' +
        '</div>' +
        // Card 4
        '<div class="kpi-card ' + dsoClass + '">' +
          '<div class="kpi-header"><span class="kpi-title">Días Cobro (DSO)</span>' + dsoBadge + '</div>' +
          '<div class="kpi-value">' + dsoText + '</div>' +
          '<div class="kpi-subtitle">Ciclo medio rotación de cartera</div>' +
          '<div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:' + dsoPct + '%;"></div></div>' +
        '</div>' +
        // Card 5
        '<div class="kpi-card ' + levClass + '">' +
          '<div class="kpi-header"><span class="kpi-title">Pasivo / Patrimonio</span>' + levBadge + '</div>' +
          '<div class="kpi-value">' + levText + '</div>' +
          '<div class="kpi-subtitle">Apalancamiento con terceros (&le; 1.5x)</div>' +
          '<div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:' + levPct + '%;"></div></div>' +
        '</div>' +
        // Card 6
        '<div class="kpi-card ' + fClass + '">' +
          '<div class="kpi-header"><span class="kpi-title">Flujo Libre de Caja</span>' + fBadge + '</div>' +
          '<div class="kpi-value" style="font-size:18px;">' + fText + '</div>' +
          '<div class="kpi-subtitle">FCO neto tras servicio de deuda</div>' +
        '</div>' +
      '</div>';
    }

    var html = '<article class="report">' +
      '<section class="result-hero tone-' + esc(r.status.tone) + '">' +
      '<div class="score-layout"><div class="gauge" style="--score:' + score + '"><div class="gauge-inner"><strong>' + score + "</strong><small>/ 100</small></div></div>" +
      '<div class="result-copy"><span class="badge">' + esc(r.status.label) + "</span><h2>" + esc(classificationText) + "</h2>" +
      '<div class="company">' + company + rut + "</div><p class=\"decision\">" + esc(r.status.message) + "</p></div></div></section>" +
      '<section class="result-section"><h2>Panel de Control y KPIs Financieros</h2>' +
      renderKpiCards(r) +
      '<div class="metrics" style="margin-top:14px;">' +
      metric("Monto aprobado", approvedValue, "Sujeto a política y validación") +
      metric("Plazo aprobado", termValue, "Máximo interno") +
      metric("Límite bruto", grossValue, "Mínimo de los límites") +
      metric("Disponible adicional", availableValue, "Después de exposición actual") +
      metric("Exposición actual", M.formatCLP(r.limits.exposure), "Facturas y pedidos comprometidos") +
      metric("Venta mensual", M.formatCLP(r.ratios.ventasMensuales), "Ventas 12m / 12") +
      '</div><p class="small muted" style="margin:10px 0 0">' + esc(statusNote(r)) + "</p></section>" +
      renderLimits(r) +
      '<section class="result-section"><h2>Desglose del scoring</h2>' + renderDimensions(r) + "</section>" +
      '<section class="result-section"><h2>Alertas y bloqueos</h2>' + renderIssues(r) + "</section>" +
      '<section class="result-section"><h2>Controles del expediente</h2>' + renderControls(r) + "</section>" +
      '<section class="result-section"><h2>Modelo predictivo (aprendizaje supervisado)</h2>' + renderPrediction(r) + "</section>" +
      renderTerm(r) +
      '<section class="result-section"><h2>Informe ejecutivo</h2><div class="metrics">' +
      metric("Analista", analyst, "Responsable de la evaluación") +
      metric("Fecha de evaluación", generated, "Generado por la herramienta") +
      metric("Puntaje", M.formatRatio(r.score, 1) + " / 100", esc(scoreHint)) +
      "</div>" + observations +
      '<p class="legal" style="margin-top:12px">Herramienta de apoyo a la decisión. No constituye una clasificación oficial de la CMF ni una probabilidad estadística de incumplimiento. La aprobación final debe ser humana, documentada y sujeta a la validación legal del plazo.</p>' +
      '<div class="report-footer"><span class="small muted">Evaluación generada el ' + esc(generated) + "</span>" +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
      '<button class="btn primary small" type="button" data-export-pdf>📄 Descargar Dictamen PDF</button> ' +
      '<button class="btn ghost small" type="button" data-print>Imprimir</button> ' +
      '<button class="btn ghost small" type="button" data-copy>Copiar resumen</button></div></div></section>' +
      "</article>";
    results.innerHTML = html;
    results.classList.remove("hidden");
    btnPrint.disabled = false;
  }

  function runEvaluation() {
    try {
      var input = toModelInput(collectForm());

      // Validación estricta Módulo 11 de RUT de la empresa
      if (input.rut && !M.isValidRut(input.rut)) {
        var clean = M.cleanRut(input.rut);
        var body = clean.slice(0, -1);
        var dv = clean.slice(-1);
        var sum = 0, mul = 2;
        for (var i = body.length - 1; i >= 0; i--) {
          sum += Number(body.charAt(i)) * mul;
          mul = mul === 7 ? 2 : mul + 1;
        }
        var res = 11 - (sum % 11);
        var expDv = res === 11 ? "0" : res === 10 ? "K" : String(res);
        showToast("RUT inválido (Módulo 11): para " + body + " el DV debe ser -" + expDv + " y no -" + dv);
      }

      var result = M.evaluate(input);
      renderResults(result);
      saveDraft();

      // Guardar en base de datos ACID relacional
      fetch(API_BASE + "/api/evaluations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: input, result: result })
      }).then(function(res) { return res.json(); })
        .then(function(data) {
          if (data.success) {
            CURRENT_EVAL_ID = data.id;
            showToast("Evaluación guardada en base de datos (Expediente #" + data.id + ")");
          }
        }).catch(function() {});

      window.requestAnimationFrame(function () {
        results.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch (error) {
      showToast("No se pudo evaluar: " + (error && error.message ? error.message : "error inesperado"));
    }
  }

  function buildSummary(r) {
    var lines = [
      "Evaluación de crédito comercial",
      "Empresa: " + (r.input.razonSocial || "Sin nombre") + " · RUT " + M.formatRut(r.input.rut),
      "Fecha: " + new Date(r.generatedAt).toLocaleString("es-CL"),
      "Analista: " + (r.input.analista || "No informado"),
      "Puntaje: " + M.formatRatio(r.score, 1) + "/100 · " + (r.status.key === "pending" ? "Provisional" : r.classification.label),
      "Decisión: " + r.status.label,
      "Monto aprobado: " + M.formatCLP(r.limits.approved),
      "Plazo aprobado: " + (r.term.approved ? r.term.approved + " días" : "No aplicable"),
      "Límite bruto: " + M.formatCLP(r.limits.gross),
      "Disponible adicional: " + M.formatCLP(r.limits.available),
      "Exposición actual: " + M.formatCLP(r.limits.exposure),
      "DSO: " + (r.ratios.dso === null ? "No informado" : Math.round(r.ratios.dso) + " días"),
      "",
      "Dimensiones:"
    ];
    r.dimensions.forEach(function (dimension) {
      lines.push("- " + dimension.label + ": " + dimension.note + "/100 (peso " + dimension.weight + "%)");
    });
    if (r.hardBlockers.length) {
      lines.push("", "Bloqueos:");
      r.hardBlockers.forEach(function (item) { lines.push("- " + item.text); });
    }
    if (r.pendingItems.length) {
      lines.push("", "Pendientes:");
      r.pendingItems.forEach(function (item) { lines.push("- " + item.text); });
    }
    if (r.warnings.length) {
      lines.push("", "Alertas:");
      r.warnings.forEach(function (item) { lines.push("- " + item.text); });
    }
    if (r.term.notes.length) {
      lines.push("", "Condiciones de plazo:");
      r.term.notes.forEach(function (note) { lines.push("- " + note); });
    }
    return lines.join("\n");
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try {
        if (document.execCommand("copy")) resolve();
        else reject(new Error("copy"));
      } catch (error) {
        reject(error);
      } finally {
        document.body.removeChild(area);
      }
    });
  }

  function copySummary() {
    if (!LAST_RESULT) return;
    copyText(buildSummary(LAST_RESULT)).then(function () {
      showToast("Resumen copiado.");
    }).catch(function () {
      showToast("No se pudo copiar el resumen.");
    });
  }

  function openHelp() {
    helpModal.classList.remove("hidden");
    helpModal.querySelector("button").focus();
  }

  function closeHelp() {
    helpModal.classList.add("hidden");
  }

  form.addEventListener("input", function () {
    updateMoneyHints();
    updateRutValidation();
    updateLiveMetrics();
    scheduleSave();
    markStale();
  });

  form.addEventListener("change", function () {
    updateMoneyHints();
    updateRutValidation();
    updateLiveMetrics();
    scheduleSave();
    markStale();
  });

  $("btnEvaluate").addEventListener("click", runEvaluation);
  btnPrint.addEventListener("click", function () { window.print(); });
  $("btnExample").addEventListener("click", function () { loadExample(); });

  if ($("selectExampleProfile")) {
    $("selectExampleProfile").addEventListener("change", function () {
      loadExample(this.value);
    });
  }

  // Guía de datos de ejemplo
  var guideModal = $("exampleGuideModal");
  function openExampleGuide() {
    if (guideModal) {
      guideModal.style.display = "flex";
      guideModal.classList.remove("hidden");
    }
  }
  function closeExampleGuide() {
    if (guideModal) {
      guideModal.style.display = "none";
      guideModal.classList.add("hidden");
    }
  }

  if ($("btnShowExampleDataGuide")) $("btnShowExampleDataGuide").addEventListener("click", openExampleGuide);
  if ($("btnCloseExampleGuide")) $("btnCloseExampleGuide").addEventListener("click", closeExampleGuide);
  if (guideModal) {
    guideModal.addEventListener("click", function (e) {
      if (e.target === guideModal) closeExampleGuide();
    });
  }
  if ($("btnApplyGuideExample")) {
    $("btnApplyGuideExample").addEventListener("click", function () {
      closeExampleGuide();
      loadExample("aprobado");
    });
  }

  $("btnReset").addEventListener("click", function () {
    if (window.confirm("¿Limpiar todos los datos y el borrador guardado?")) resetForm();
  });
  $("btnDiscardDraft").addEventListener("click", function () {
    resetForm();
    showToast("Borrador descartado.");
  });
  $("btnHelp").addEventListener("click", openHelp);
  if ($("btnSii")) $("btnSii").addEventListener("click", function () {
    var rutValue = $("rut").value;
    if (!M.isValidRut(M.cleanRut(rutValue))) { showToast("RUT inválido"); return; }
    showToast("Consultando SII...");
    var btn = $("btnSii");
    if (btn) { btn.disabled = true; btn.textContent = "Consultando..."; }

    var pBox = $("siiProgressBox");
    var pText = $("siiProgressText");
    var pBar = $("siiProgressBar");
    var pPct = $("siiProgressPct");
    var progressTimer = null;

    if (pBox) {
      pBox.classList.remove("hidden");
      var currentStep = 15;
      pText.textContent = "Conectando con portal del SII...";
      pBar.style.width = "15%";
      pPct.textContent = "15%";

      progressTimer = setInterval(function () {
        if (currentStep < 85) {
          currentStep += Math.floor(Math.random() * 12) + 5;
          if (currentStep > 85) currentStep = 85;
          pBar.style.width = currentStep + "%";
          pPct.textContent = currentStep + "%";
          if (currentStep > 40 && currentStep <= 65) {
            pText.textContent = "Extrayendo situación tributaria y timbraje...";
          } else if (currentStep > 65) {
            pText.textContent = "Procesando actividades económicas...";
          }
        }
      }, 700);
    }

    fetch(API_BASE + "/api/sii?rut=" + encodeURIComponent(rutValue))
      .then(function (response) { return response.json(); })
      .then(function (data) {
        clearInterval(progressTimer);
        if (pBar) pBar.style.width = "100%";
        if (pPct) pPct.textContent = "100%";
        if (pText) pText.textContent = "Datos obtenidos exitosamente.";

        setTimeout(function() {
          if (pBox) pBox.classList.add("hidden");
        }, 1200);

        if (btn) { btn.disabled = false; btn.textContent = "Consultar SII"; }

        if (data.error) { showToast(data.error); return; }
        if (data.nombre && $("razonSocial")) {
          $("razonSocial").value = data.nombre;
          $("razonSocial").dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (data.rut && $("rutERut")) {
          $("rutERut").value = data.rut;
          $("rutERut").dispatchEvent(new Event("input", { bubbles: true }));
        }
        if (data.inicioActividades === "SI") {
          $("inicioVigente").value = "1";
          if ($("sociedadVigente")) $("sociedadVigente").checked = true;
        } else if (data.inicioActividades === "NO") {
          $("inicioVigente").value = "0";
        }
        if (data.antiguedad !== null && data.antiguedad !== undefined) {
          $("antiguedad").value = data.antiguedad;
        }

        // Mostrar Cápsula de Compliance SII
        var capsule = $("siiCapsule");
        if (capsule) {
          capsule.classList.remove("hidden");
          var tBadge = $("siiTimbrajeBadge");
          if (tBadge) {
            if (data.anioTimbraje) {
              tBadge.textContent = "Factura Electrónica: " + data.anioTimbraje;
              tBadge.style.background = "#dcfce7";
              tBadge.style.color = "#166534";
            } else {
              tBadge.textContent = "Timbraje: No informado";
              tBadge.style.background = "#fef3c7";
              tBadge.style.color = "#92400e";
            }
          }
          if ($("siiActividadText")) {
            $("siiActividadText").textContent = "Giro: " + (data.actividad || "Sin giro especificado") + (data.codActividad ? " (" + data.codActividad + ")" : "");
          }
          if ($("siiIvaText")) {
            $("siiIvaText").textContent = "Afecta a IVA: " + (data.afectaIva || "Sí (Primera Categoría)");
          }
          if ($("siiTamanoText")) {
            $("siiTamanoText").textContent = "Tamaño: " + (data.empresaMenorTamano === "SI" ? "PyME (Ley 20.416)" : "Empresa General");
          }
          if ($("siiInicioText")) {
            $("siiInicioText").textContent = "Inicio: " + (data.fechaInicioActividades || "Vigente");
          }

          var docsList = $("siiDocsTimbradosList");
          if (docsList) {
            docsList.innerHTML = "";
            var docs = data.documentosTimbrados || [];
            if (docs.length > 0) {
              var currentYear = new Date().getFullYear();
              docs.forEach(function(item) {
                var isRecent = Number(item.anio) >= (currentYear - 1);
                var pill = document.createElement("span");
                pill.style.display = "inline-flex";
                pill.style.alignItems = "center";
                pill.style.gap = "4px";
                pill.style.padding = "2px 6px";
                pill.style.borderRadius = "4px";
                pill.style.fontSize = "10.5px";
                pill.style.fontWeight = "500";
                pill.style.background = isRecent ? "#dcfce7" : "#f1f5f9";
                pill.style.color = isRecent ? "#166534" : "#475569";
                pill.style.border = "1px solid " + (isRecent ? "#86efac" : "#cbd5e1");
                pill.textContent = item.documento + " (" + item.anio + ")";
                docsList.appendChild(pill);
              });
            } else if (data.anioTimbraje) {
              var pill = document.createElement("span");
              pill.style.padding = "2px 6px";
              pill.style.borderRadius = "4px";
              pill.style.fontSize = "10.5px";
              pill.style.background = "#dcfce7";
              pill.style.color = "#166534";
              pill.textContent = "Factura Electrónica (" + data.anioTimbraje + ")";
              docsList.appendChild(pill);
            } else {
              docsList.innerHTML = '<span style="font-size:11px; color:#64748b;">No registra documentos autorizados recientes.</span>';
            }
          }
        }

        updateMoneyHints();
        updateRutValidation();
        updateLiveMetrics();
        scheduleSave();
        showToast("Datos SII cargados: " + (data.nombre || rutValue));
      })
      .catch(function () {
        clearInterval(progressTimer);
        if (pBox) pBox.classList.add("hidden");
        if (btn) { btn.disabled = false; btn.textContent = "Consultar SII"; }
        showToast("Error consultando SII");
      });
  });
  $("btnCloseHelp").addEventListener("click", closeHelp);
  helpModal.addEventListener("click", function (event) {
    if (event.target === helpModal) closeHelp();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !helpModal.classList.contains("hidden")) closeHelp();
  });
  results.addEventListener("click", function (event) {
    var target = event.target.closest("[data-print], [data-copy], [data-ml-feedback], [data-ml-train], [data-ml-reset]");
    if (!target) return;
    // data-export-pdf NO se maneja aquí: lo gestiona el handler comercial dedicado
    // (handleExportPdfClick) para evitar descargas duplicadas.
    if (target.hasAttribute("data-print")) window.print();
    if (target.hasAttribute("data-copy")) copySummary();
    if (target.hasAttribute("data-ml-feedback")) {
      var label = target.getAttribute("data-ml-feedback");
      var list = loadFeedback();
      if (LAST_RESULT) {
        list.push({ input: LAST_RESULT.input, label: label });
        saveFeedback(list);
        showToast("Feedback guardado (" + list.length + ").");
      }
    }
    if (target.hasAttribute("data-ml-train")) {
      var ml = window.CreditML;
      var list2 = loadFeedback();
      if (ml && ml.fit) {
        var res = ml.fit(list2, { epochs: 10, lr: 0.05 });
        showToast(res.ok ? ("Modelo reentrenado con " + res.samples + " muestras.") : (res.message || "Error"));
        if (LAST_RESULT) runEvaluation();
      }
    }
    if (target.hasAttribute("data-ml-reset")) {
      var ml2 = window.CreditML;
      if (ml2 && ml2.reset) ml2.reset();
      showToast("Modelo reiniciado.");
      if (LAST_RESULT) runEvaluation();
    }
  });

  // --- Lógica del Modelo Comercial Híbrido ---
  function setCommercialMode(mode) {
    CURRENT_MODE = mode;
    var btnMan = $("btnModeManual");
    var btnAut = $("btnModeAuto");
    var stepDocs = $("stepDocsCard");
    var noteMan = $("stepDocsManualNote");
    var noteAut = $("stepDocsAutoNote");
    var badgeDocs = $("stepDocsModeBadge");

    var actMan = btnMan ? btnMan.querySelector(".saas-card-action") : null;
    var actAut = btnAut ? btnAut.querySelector(".saas-card-action") : null;

    if (mode === "manual") {
      if (btnMan) {
        btnMan.classList.add("active");
        btnMan.style.background = "";
        btnMan.style.color = "";
        if (actMan) actMan.textContent = "Seleccionado";
      }
      if (btnAut) {
        btnAut.classList.remove("active");
        btnAut.style.background = "";
        btnAut.style.color = "";
        if (actAut) actAut.textContent = "Habilitar";
      }
      if (noteMan) noteMan.style.display = "block";
      if (noteAut) noteAut.style.display = "none";
      if (badgeDocs) {
        badgeDocs.textContent = "Opcional en modo manual";
        badgeDocs.style.background = "#e2e8f0";
        badgeDocs.style.color = "#475569";
      }
      showToast("Modo activo: Evaluación Manual Gratuita");
    } else {
      if (btnAut) {
        btnAut.classList.add("active");
        btnAut.style.background = "";
        btnAut.style.color = "";
        if (actAut) actAut.textContent = "Seleccionado";
      }
      if (btnMan) {
        btnMan.classList.remove("active");
        btnMan.style.background = "";
        btnMan.style.color = "";
        if (actMan) actMan.textContent = "Habilitar";
      }
      if (noteMan) noteMan.style.display = "none";
      if (noteAut) noteAut.style.display = "block";
      if (badgeDocs) {
        badgeDocs.textContent = "Recomendado: Adjunta tus PDFs";
        badgeDocs.style.background = "#dcfce7";
        badgeDocs.style.color = "#166534";
      }
      if (stepDocs) stepDocs.open = true;
      showToast("Modo activo: Evaluación Documental Automatizada");
    }
  }

  function downloadReportPdf(isForcePreliminary) {
    if (!LAST_RESULT) return;
    var useToken = isForcePreliminary ? "" : ACTIVE_CREDIT_TOKEN;
    showToast(useToken ? "Generando Dictamen Oficial..." : "Generando informe...");
    
    fetch(API_BASE + "/api/report-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input: LAST_RESULT.input,
        result: LAST_RESULT,
        mode: CURRENT_MODE,
        token: useToken,
        order_id: useToken,
        eval_id: CURRENT_EVAL_ID
      })
    })
    .then(function(res) {
      if (!res.ok) throw new Error("Error en servidor");
      var repType = res.headers.get("X-Report-Type");
      return res.blob().then(function(blob) { return { blob: blob, type: repType }; });
    })
    .then(function(data) {
      var url = window.URL.createObjectURL(data.blob);
      var a = document.createElement("a");
      a.href = url;
      var rut = (LAST_RESULT.input.rut || "Comercial");
      a.download = (data.type === "official" ? "Dictamen_Credito_Oficial_" : "Dictamen_Preliminar_") + rut + ".pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      if (data.type === "official") {
        showToast("Dictamen Oficial descargado con éxito.");
        refreshCreditStatus();
      } else {
        showToast("Copia preliminar descargada.");
      }
    })
    .catch(function(err) {
      showToast("No se pudo generar el PDF");
    });
  }

  function handleExportPdfClick() {
    if (!LAST_RESULT) return;
    // Si ya cuenta con token de pago o crédito activo, descarga el dictamen oficial directamente
    if (ACTIVE_CREDIT_TOKEN) {
      downloadReportPdf(false);
      return;
    }
    // Si está en modo manual gratuito y no tiene crédito, abre el modal de actualización comercial
    var upModal = $("upgradeModal");
    if (upModal) {
      upModal.style.display = "flex";
      upModal.classList.remove("hidden");
    } else {
      downloadReportPdf(true);
    }
  }

  var CURRENT_CREDIT_DATA = null;

  function openCreditPanel() {
    var pModal = $("creditPanelModal");
    if (!pModal) return;
    pModal.style.display = "flex";
    pModal.classList.remove("hidden");
    updateCreditPanelUI();
  }

  function closeCreditPanel() {
    var pModal = $("creditPanelModal");
    if (!pModal) return;
    pModal.style.display = "none";
    pModal.classList.add("hidden");
  }

  function updateCreditPanelUI() {
    var activeSec = $("panelActiveSection");
    var emptySec = $("panelEmptySection");
    if (!ACTIVE_CREDIT_TOKEN || !CURRENT_CREDIT_DATA || !CURRENT_CREDIT_DATA.valid) {
      if (activeSec) activeSec.style.display = "none";
      if (emptySec) emptySec.style.display = "block";
      return;
    }

    if (emptySec) emptySec.style.display = "none";
    if (activeSec) activeSec.style.display = "block";

    var d = CURRENT_CREDIT_DATA;
    if ($("panelPlanTitle")) $("panelPlanTitle").textContent = d.plan_nombre || "Paquete de Informes";
    if ($("panelCreditsRemaining")) $("panelCreditsRemaining").textContent = d.creditos_restantes;
    if ($("panelCreditsTotal")) $("panelCreditsTotal").textContent = d.creditos_totales;

    var pct = Math.round((d.creditos_restantes / Math.max(1, d.creditos_totales)) * 100);
    var pBar = $("panelProgressBar");
    if (pBar) pBar.style.width = pct + "%";

    var tBox = $("panelTokenMasked");
    if (tBox) tBox.textContent = ACTIVE_CREDIT_TOKEN;

    var oRef = $("panelOrderRef");
    if (oRef) oRef.textContent = d.order_id_masked || "ORD-COMPRA";

    var invLink = $("panelInvoiceLink");
    if (invLink && d.invoice_url) {
      invLink.href = API_BASE + d.invoice_url;
      invLink.style.display = "inline-block";
    }

    var badge = $("panelStatusBadge");
    if (badge) {
      if (d.creditos_restantes > 0) {
        badge.textContent = d.creditos_restantes + " disponibles (" + pct + "%)";
        badge.style.background = "#dcfce7";
        badge.style.color = "#166534";
      } else {
        badge.textContent = "Créditos Agotados";
        badge.style.background = "#fee2e2";
        badge.style.color = "#991b1b";
      }
    }
  }

  function refreshCreditStatus() {
    var topBadge = $("btnCreditsTopBadge");
    var topText = $("creditsTopText");

    if (!ACTIVE_CREDIT_TOKEN) {
      CURRENT_CREDIT_DATA = null;
      var banner = $("creditStatusBanner");
      if (banner) banner.style.display = "none";
      if (topBadge && topText) {
        topText.textContent = "Sin Plan Activo";
        topBadge.style.background = "#f1f5f9";
        topBadge.style.color = "#475569";
        topBadge.style.borderColor = "#cbd5e1";
      }
      return;
    }

    fetch(API_BASE + "/api/payments/credit-status?token=" + encodeURIComponent(ACTIVE_CREDIT_TOKEN))
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.valid) {
          CURRENT_CREDIT_DATA = data;
          // Actualizar botón de cabecera
          if (topBadge && topText) {
            topText.textContent = data.creditos_restantes + " Crédito(s)";
            topBadge.style.background = data.creditos_restantes > 0 ? "#f0fdf4" : "#fee2e2";
            topBadge.style.color = data.creditos_restantes > 0 ? "#166534" : "#991b1b";
            topBadge.style.borderColor = data.creditos_restantes > 0 ? "#86efac" : "#fca5a5";
          }

          if (data.creditos_restantes > 0) {
            var banner = $("creditStatusBanner");
            if (banner) {
              banner.style.display = "block";
              if ($("creditPlanName")) $("creditPlanName").textContent = data.plan_nombre || "Paquete de Informes";
              if ($("creditAvailableCount")) $("creditAvailableCount").textContent = data.creditos_restantes;
            }
          } else {
            var banner2 = $("creditStatusBanner");
            if (banner2) banner2.style.display = "none";
            showToast("Has consumido los créditos de este paquete.");
          }
          updateCreditPanelUI();
        } else {
          ACTIVE_CREDIT_TOKEN = "";
          localStorage.removeItem("creditob2b_active_token");
          refreshCreditStatus();
        }
      })
      .catch(function() {});
  }

  // Event Listeners de Modo Comercial y Modales
  if ($("btnModeManual")) $("btnModeManual").addEventListener("click", function() { setCommercialMode("manual"); });
  if ($("btnModeAuto")) $("btnModeAuto").addEventListener("click", function() { setCommercialMode("automated"); });

  if ($("btnRedeemCredit")) $("btnRedeemCredit").addEventListener("click", function() {
    var rModal = $("redeemModal");
    if (rModal) {
      rModal.style.display = "flex";
      rModal.classList.remove("hidden");
      setTimeout(function() { if ($("inputRedeemCode")) $("inputRedeemCode").focus(); }, 80);
    }
  });

  if ($("btnCloseRedeemModal")) $("btnCloseRedeemModal").addEventListener("click", function() {
    var rModal = $("redeemModal");
    if (rModal) { rModal.style.display = "none"; rModal.classList.add("hidden"); }
  });

  if ($("btnCloseUpgradeModal")) $("btnCloseUpgradeModal").addEventListener("click", function() {
    var upModal = $("upgradeModal");
    if (upModal) { upModal.style.display = "none"; upModal.classList.add("hidden"); }
  });

  if ($("btnDownloadPreliminary")) $("btnDownloadPreliminary").addEventListener("click", function() {
    var upModal = $("upgradeModal");
    if (upModal) { upModal.style.display = "none"; upModal.classList.add("hidden"); }
    downloadReportPdf(true);
  });

  if ($("btnHaveCodeLink")) $("btnHaveCodeLink").addEventListener("click", function() {
    var upModal = $("upgradeModal");
    if (upModal) { upModal.style.display = "none"; upModal.classList.add("hidden"); }
    var rModal = $("redeemModal");
    if (rModal) {
      rModal.style.display = "flex";
      rModal.classList.remove("hidden");
      setTimeout(function() { if ($("inputRedeemCode")) $("inputRedeemCode").focus(); }, 80);
    }
  });

  if ($("btnValidateRedeem")) $("btnValidateRedeem").addEventListener("click", function() {
    var code = ($("inputRedeemCode") ? $("inputRedeemCode").value : "").trim();
    if (!code) { showToast("Ingresa tu token de acceso secreto"); return; }
    
    var btn = $("btnValidateRedeem");
    btn.disabled = true;
    btn.textContent = "Verificando...";

    fetch(API_BASE + "/api/payments/credit-status?token=" + encodeURIComponent(code))
      .then(function(res) { return res.json(); })
      .then(function(data) {
        btn.disabled = false;
        btn.textContent = "Verificar y Activar Créditos";
        if (data.valid && data.creditos_restantes > 0) {
          ACTIVE_CREDIT_TOKEN = code;
          localStorage.setItem("creditob2b_active_token", code);
          var rModal = $("redeemModal");
          if (rModal) { rModal.style.display = "none"; rModal.classList.add("hidden"); }
          showToast("¡Créditos activados! Dispones de " + data.creditos_restantes + " informe(s) oficial(es).");
          refreshCreditStatus();
        } else if (data.valid && data.creditos_restantes <= 0) {
          showToast("Este token ya no tiene créditos disponibles.");
        } else {
          showToast(data.message || "Token de acceso no válido");
        }
      })
      .catch(function() {
        btn.disabled = false;
        btn.textContent = "Verificar y Activar Créditos";
        showToast("Error de conexión al validar token");
      });
  });

  if ($("btnClearCreditToken")) $("btnClearCreditToken").addEventListener("click", function() {
    ACTIVE_CREDIT_TOKEN = "";
    localStorage.removeItem("creditob2b_active_token");
    refreshCreditStatus();
    showToast("Código de créditos desvinculado.");
  });

  // Event Listeners del Panel de Créditos
  if ($("btnCreditsTopBadge")) $("btnCreditsTopBadge").addEventListener("click", openCreditPanel);
  if ($("btnCloseCreditPanel")) $("btnCloseCreditPanel").addEventListener("click", closeCreditPanel);

  if ($("btnCopyActiveToken")) $("btnCopyActiveToken").addEventListener("click", function() {
    if (!ACTIVE_CREDIT_TOKEN) return;
    copyText(ACTIVE_CREDIT_TOKEN).then(function() {
      showToast("Token copiado al portapapeles.");
    }).catch(function() {
      showToast("Token: " + ACTIVE_CREDIT_TOKEN);
    });
  });

  if ($("btnPanelOpenRedeem")) $("btnPanelOpenRedeem").addEventListener("click", function() {
    closeCreditPanel();
    var rModal = $("redeemModal");
    if (rModal) {
      rModal.style.display = "flex";
      rModal.classList.remove("hidden");
      setTimeout(function() { if ($("inputRedeemCode")) $("inputRedeemCode").focus(); }, 80);
    }
  });

  if ($("btnPanelChangeToken")) $("btnPanelChangeToken").addEventListener("click", function() {
    closeCreditPanel();
    ACTIVE_CREDIT_TOKEN = "";
    localStorage.removeItem("creditob2b_active_token");
    refreshCreditStatus();
    var rModal = $("redeemModal");
    if (rModal) {
      rModal.style.display = "flex";
      rModal.classList.remove("hidden");
      setTimeout(function() { if ($("inputRedeemCode")) $("inputRedeemCode").focus(); }, 80);
    }
  });

  // Gestor comercial de descarga de PDF (token/crédito/modal de actualización)
  results.addEventListener("click", function (event) {
    var target = event.target.closest("[data-export-pdf]");
    if (target) {
      event.preventDefault();
      handleExportPdfClick();
    }
  }, true);

  populateSelects();
  applySelectDefaults();
  bindFileLabels();
  loadDraft();
  // Si no se cargó un borrador que haya renderizado la lista, renderizarla desde el valor inicial
  if (!$("repListContainer").children.length) {
    renderRepList(getRepList());
  }
  updateMoneyHints();
  updateRutValidation();
  updateLiveMetrics();
  refreshCreditStatus();
  })();
