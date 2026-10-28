(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CreditModel = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var SECTORS = {
    servicios_ti: { label: "Servicios TI / Software / Consultoría", margenBueno: 0.12, margenAceptable: 0.06 },
    comercio_hardware: { label: "Comercio y reacondicionamiento de equipos", margenBueno: 0.07, margenAceptable: 0.03 },
    distribucion: { label: "Distribución / mayorista", margenBueno: 0.05, margenAceptable: 0.02 },
    manufactura: { label: "Manufactura / industria", margenBueno: 0.08, margenAceptable: 0.04 },
    construccion: { label: "Construcción / montaje", margenBueno: 0.06, margenAceptable: 0.02 },
    otro: { label: "Otro / mixto", margenBueno: 0.08, margenAceptable: 0.03 }
  };

  var WEIGHTS = { liquidez: 20, rentabilidad: 25, endeudamiento: 20, pago: 25, estabilidad: 10 };

  var PAYMENT_HISTORY = {
    puntual: { label: "Puntual", score: 100 },
    atraso_leve: { label: "Atraso leve (1–15 días)", score: 75 },
    atraso_moderado: { label: "Atraso moderado (16–30 días)", score: 45 },
    atraso_grave: { label: "Atraso grave (>30 días)", score: 0 },
    sin_historial: { label: "Sin historial con la empresa", score: 50 }
  };

  var DOC_LABELS = {
    trib: "Carpeta tributaria",
    erut: "e-RUT",
    cmf: "Informe de deudas CMF",
    escritura: "Escritura / estatutos",
    eecc: "Estados financieros"
  };

  var REQUIRED_DOCS = ["trib", "erut", "cmf", "escritura", "eecc"];

  var STATUS = {
    approved: {
      key: "approved",
      label: "APROBADO",
      tone: "ok",
      message: "Cumple la política. Se recomienda otorgar la línea y plazo indicados, sujeto a validación humana y legal."
    },
    conditional: {
      key: "conditional",
      label: "APROBADO CON CONDICIONES",
      tone: "ok",
      message: "Cumple con condiciones. Se recomienda aprobar el límite y plazo indicados, con revisión de jefatura."
    },
    review: {
      key: "review",
      label: "REVISIÓN / CRÉDITO RESTRINGIDO",
      tone: "warn",
      message: "Presenta señales de riesgo. Se recomienda reducir límite, exigir mitigantes y revisión de jefatura."
    },
    no_ordinary: {
      key: "no_ordinary",
      label: "SIN LÍNEA ORDINARIA",
      tone: "warn",
      message: "No se recomienda línea ordinaria. Evaluar prepago, garantía real o una revisión especial."
    },
    rejected: {
      key: "rejected",
      label: "RECHAZADO",
      tone: "bad",
      message: "No cumple los mínimos de la política. No otorgar crédito sin cambios sustanciales."
    },
    blocked: {
      key: "blocked",
      label: "RECHAZADO / BLOQUEADO",
      tone: "bad",
      message: "Existen bloqueos críticos. No otorgar crédito hasta resolverlos."
    },
    pending: {
      key: "pending",
      label: "PENDIENTE DE ANTECEDENTES",
      tone: "info",
      message: "Faltan antecedentes obligatorios. El puntaje es provisional y no habilita aprobación."
    },
    no_availability: {
      key: "no_availability",
      label: "SIN DISPONIBILIDAD ADICIONAL",
      tone: "warn",
      message: "La exposición actual consume el límite. No otorgar nuevo crédito hasta reducir saldos o ampliar la política con aprobación."
    }
  };

  var clpFormatter = new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 });

  function isNum(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function toNum(value, fallback) {
    var resolvedFallback = fallback === undefined ? null : fallback;
    if (value === null || value === undefined || value === "") return resolvedFallback;
    if (typeof value === "number") return Number.isFinite(value) ? value : resolvedFallback;
    var text = String(value).trim();
    if (!text) return resolvedFallback;
    var dots = (text.match(/\./g) || []).length;
    if (text.indexOf(",") >= 0 && dots > 0) text = text.replace(/\./g, "").replace(",", ".");
    else if (text.indexOf(",") >= 0) text = text.replace(",", ".");
    else if (dots > 1) text = text.replace(/\./g, "");
    var parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : resolvedFallback;
  }

  function toBool(value, fallback) {
    if (value === null || value === undefined || value === "") return fallback;
    if (typeof value === "boolean") return value;
    return ["0", "false", "no", "n", "off"].indexOf(String(value).trim().toLowerCase()) < 0;
  }

  function ratio(numerator, denominator) {
    if (!isNum(numerator) || !isNum(denominator) || denominator === 0) return null;
    return numerator / denominator;
  }

  function clamp(value, min, max) {
    if (!isNum(value)) return min;
    return Math.max(min, Math.min(max, value));
  }

  function scoreHigher(value, bands) {
    if (!isNum(value)) return 0;
    for (var i = 0; i < bands.length; i += 1) {
      if (value >= bands[i][0]) return bands[i][1];
    }
    return 0;
  }

  function scoreLower(value, bands) {
    if (!isNum(value)) return 0;
    for (var i = 0; i < bands.length; i += 1) {
      if (value <= bands[i][0]) return bands[i][1];
    }
    return 0;
  }

  function cleanRut(value) {
    return String(value === null || value === undefined ? "" : value).replace(/[^0-9kK]/g, "").toUpperCase();
  }

  function isValidRut(value) {
    var clean = cleanRut(value);
    if (clean.length < 2) return false;
    var body = clean.slice(0, -1);
    var dv = clean.slice(-1);
    var sum = 0;
    var multiplier = 2;
    for (var i = body.length - 1; i >= 0; i -= 1) {
      sum += Number(body.charAt(i)) * multiplier;
      multiplier = multiplier === 7 ? 2 : multiplier + 1;
    }
    var result = 11 - (sum % 11);
    var expected = result === 11 ? "0" : result === 10 ? "K" : String(result);
    return expected === dv;
  }

  function formatRut(value) {
    var clean = cleanRut(value);
    if (clean.length < 2) return "";
    var body = clean.slice(0, -1);
    var dv = clean.slice(-1);
    var withDots = body.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return withDots + "-" + dv;
  }

  function parseRutList(value) {
    if (Array.isArray(value)) return value.map(cleanRut).filter(Boolean);
    return String(value === null || value === undefined ? "" : value)
      .split(/[\n,;]+/)
      .map(cleanRut)
      .filter(Boolean);
  }

  function formatCLP(value) {
    if (!isNum(value)) return "—";
    return clpFormatter.format(Math.round(value));
  }

  function formatPct(value, decimals) {
    if (!isNum(value)) return "—";
    var places = decimals === undefined ? 1 : decimals;
    return (value * 100).toFixed(places).replace(".", ",") + "%";
  }

  function formatRatio(value, decimals) {
    if (!isNum(value)) return "—";
    var places = decimals === undefined ? 2 : decimals;
    return value.toFixed(places).replace(".", ",");
  }

  function normalize(raw) {
    var source = raw || {};
    var docs = source.docs || {};
    return {
      razonSocial: String(source.razonSocial || "").trim(),
      rut: cleanRut(source.rut),
      rutERut: cleanRut(source.rutERut),
      rutSolicitante: cleanRut(source.rutSolicitante),
      representantes: parseRutList(source.representantes),
      sector: SECTORS[source.sector] ? source.sector : "otro",
      antiguedad: toNum(source.antiguedad),
      ventas12m: toNum(source.ventas12m),
      montoSolicitado: toNum(source.montoSolicitado, 0),
      plazo: toNum(source.plazo, 0),
      exposicionActual: toNum(source.exposicionActual, 0),
      concentracionTopCliente: toNum(source.concentracionTopCliente),
      activoCorriente: toNum(source.activoCorriente),
      pasivoCorriente: toNum(source.pasivoCorriente),
      inventarios: toNum(source.inventarios),
      caja: toNum(source.caja),
      cuentasPorCobrar: toNum(source.cuentasPorCobrar),
      ebitda: toNum(source.ebitda),
      flujoCajaOperacional: toNum(source.flujoCajaOperacional),
      gastosFinancieros: toNum(source.gastosFinancieros),
      servicioDeuda: toNum(source.servicioDeuda),
      pasivoTotal: toNum(source.pasivoTotal),
      patrimonio: toNum(source.patrimonio),
      deudaFinanciera: toNum(source.deudaFinanciera),
      deudaFinancieraCP: toNum(source.deudaFinancieraCP),
      deudaSociosRelacionados: toNum(source.deudaSociosRelacionados),
      diferenciaCambio: toNum(source.diferenciaCambio),
      maxDiasMora: toNum(source.maxDiasMora, 0),
      deudaVencida: toNum(source.deudaVencida, 0),
      deudaCastigada: toNum(source.deudaCastigada, 0),
      instituciones: toNum(source.instituciones, 0),
      protestos: toNum(source.protestos, 0),
      morosidades: toNum(source.morosidades, 0),
      montoMorosidades: toNum(source.montoMorosidades, 0),
      pagoHistorico: PAYMENT_HISTORY[source.pagoHistorico] ? source.pagoHistorico : "sin_historial",
      facturasVencidas: toNum(source.facturasVencidas, 0),
      situacionTributaria: ["ok", "esp", "deu"].indexOf(source.situacionTributaria) >= 0 ? source.situacionTributaria : "ok",
      deudaTGR: toNum(source.deudaTGR, 0),
      f29SinDeclarar: toNum(source.f29SinDeclarar, 0),
      inicioVigente: toBool(source.inicioVigente, true),
      sociedadVigente: toBool(source.sociedadVigente, true),
      facultades: toBool(source.facultades, true),
      eeccVerificados: toBool(source.eeccVerificados, false),
      docs: {
        trib: toBool(docs.trib, false),
        erut: toBool(docs.erut, false),
        cmf: toBool(docs.cmf, false),
        escritura: toBool(docs.escritura, false),
        eecc: toBool(docs.eecc, false),
        dicom: toBool(docs.dicom, false)
      },
      aval: toBool(source.aval, false),
      garantia: toBool(source.garantia, false),
      seguroCredito: toBool(source.seguroCredito, false),
      validacionLegal: toBool(source.validacionLegal, false),
      autorizacion90: toBool(source.autorizacion90, false),
      justificacion90: toBool(source.justificacion90, false),
      limitePoliticaRiesgo: (source.limitePoliticaRiesgo !== undefined && source.limitePoliticaRiesgo !== null && String(source.limitePoliticaRiesgo).trim() !== "") ? toNum(source.limitePoliticaRiesgo, null) : null,
      factorComercial: toNum(source.factorComercial, 0.9),
      multiplicadorFlujo: toNum(source.multiplicadorFlujo, 1),
      tendenciaVentas: ["sube", "estable", "cae", ""].indexOf(source.tendenciaVentas) >= 0 ? source.tendenciaVentas : "",
      analista: String(source.analista || "").trim(),
      observaciones: String(source.observaciones || "").trim()
    };
  }

  function ratios(input) {
    var ventasMensuales = input.ventas12m > 0 ? input.ventas12m / 12 : null;
    var razonCorriente;
    if (input.pasivoCorriente === 0) {
      razonCorriente = input.activoCorriente > 0 ? 999 : input.activoCorriente === 0 ? 0 : null;
    } else {
      razonCorriente = ratio(input.activoCorriente, input.pasivoCorriente);
    }
    var pruebaAcida;
    if (input.pasivoCorriente === 0) {
      var acidBase = input.activoCorriente !== null && input.inventarios !== null ? input.activoCorriente - input.inventarios : null;
      pruebaAcida = acidBase !== null ? (acidBase > 0 ? 999 : 0) : null;
    } else {
      var acid = input.activoCorriente !== null && input.inventarios !== null ? input.activoCorriente - input.inventarios : null;
      pruebaAcida = ratio(acid, input.pasivoCorriente);
    }
    var capitalTrabajo = input.activoCorriente !== null && input.pasivoCorriente !== null ? input.activoCorriente - input.pasivoCorriente : null;
    var capitalTrabajoRatio = capitalTrabajo !== null && ventasMensuales !== null && ventasMensuales > 0 ? capitalTrabajo / ventasMensuales : null;
    var margenEbitda = ratio(input.ebitda, input.ventas12m);
    var flujoMargen = ratio(input.flujoCajaOperacional, input.ventas12m);
    var coberturaIntereses;
    if (input.gastosFinancieros === null || input.gastosFinancieros === undefined) {
      coberturaIntereses = null;
    } else if (input.gastosFinancieros === 0) {
      coberturaIntereses = input.deudaFinanciera !== null && input.deudaFinanciera > 0 ? null : (input.ebitda !== null ? 999 : null);
    } else {
      coberturaIntereses = ratio(input.ebitda, input.gastosFinancieros);
    }
    var coberturaServicio;
    if (input.servicioDeuda === null || input.servicioDeuda === undefined) {
      coberturaServicio = null;
    } else if (input.servicioDeuda === 0) {
      coberturaServicio = input.deudaFinanciera !== null && input.deudaFinanciera > 0 ? null : (input.flujoCajaOperacional !== null ? 999 : null);
    } else {
      coberturaServicio = ratio(input.flujoCajaOperacional, input.servicioDeuda);
    }
    var deudaPatrimonio;
    if (input.patrimonio === null) deudaPatrimonio = null;
    else if (input.patrimonio <= 0) deudaPatrimonio = input.pasivoTotal === null ? null : 999;
    else deudaPatrimonio = ratio(input.pasivoTotal, input.patrimonio);
    var deudaNeta = input.deudaFinanciera !== null && input.deudaFinanciera !== undefined
      ? input.deudaFinanciera - (input.caja || 0)
      : null;
    var deudaNetaEbitda = null;
    if (deudaNeta !== null && input.ebitda !== null) {
      if (input.ebitda > 0) deudaNetaEbitda = deudaNeta / input.ebitda;
      else deudaNetaEbitda = deudaNeta <= 0 ? -1 : 999;
    }
    var cajaDeudaCP;
    if (input.deudaFinancieraCP === null || input.deudaFinancieraCP === undefined) {
      cajaDeudaCP = null;
    } else if (input.deudaFinancieraCP === 0) {
      cajaDeudaCP = input.caja !== null && input.caja !== undefined ? 999 : null;
    } else {
      cajaDeudaCP = ratio(input.caja, input.deudaFinancieraCP);
    }
    var deudaCPShare;
    if (input.deudaFinanciera === null || input.deudaFinanciera === undefined) deudaCPShare = null;
    else if (input.deudaFinanciera === 0) deudaCPShare = input.deudaFinancieraCP > 0 ? 1 : 0;
    else deudaCPShare = ratio(input.deudaFinancieraCP, input.deudaFinanciera);
    var vencidaRatio;
    if (input.deudaFinanciera === null || input.deudaFinanciera === undefined) vencidaRatio = null;
    else if (input.deudaFinanciera === 0) vencidaRatio = input.deudaVencida > 0 ? 1 : 0;
    else vencidaRatio = ratio(input.deudaVencida, input.deudaFinanciera);
    var facturasVencidasRatio;
    if (ventasMensuales === null) facturasVencidasRatio = null;
    else if (ventasMensuales === 0) facturasVencidasRatio = input.facturasVencidas > 0 ? 1 : 0;
    else facturasVencidasRatio = ratio(input.facturasVencidas, ventasMensuales);
    var flujoLibre = input.flujoCajaOperacional !== null && input.flujoCajaOperacional !== undefined
      ? input.flujoCajaOperacional - (input.servicioDeuda || 0)
      : null;
    var dso = input.cuentasPorCobrar !== null && input.ventas12m > 0
      ? input.cuentasPorCobrar / input.ventas12m * 365
      : null;

    return {
      ventasMensuales: ventasMensuales,
      razonCorriente: razonCorriente,
      pruebaAcida: pruebaAcida,
      capitalTrabajo: capitalTrabajo,
      capitalTrabajoRatio: capitalTrabajoRatio,
      margenEbitda: margenEbitda,
      flujoMargen: flujoMargen,
      coberturaIntereses: coberturaIntereses,
      coberturaServicio: coberturaServicio,
      deudaPatrimonio: deudaPatrimonio,
      deudaNeta: deudaNeta,
      deudaNetaEbitda: deudaNetaEbitda,
      cajaDeudaCP: cajaDeudaCP,
      deudaCPShare: deudaCPShare,
      vencidaRatio: vencidaRatio,
      facturasVencidasRatio: facturasVencidasRatio,
      flujoLibre: flujoLibre,
      dso: dso,
      deudaTotalExterna: (input.deudaFinanciera || 0) + (input.deudaTGR || 0) + (input.montoMorosidades || 0) + (input.deudaSociosRelacionados || 0)
    };
  }

  function makeIndicator(label, value, score, display, missing) {
    return {
      label: label,
      value: value,
      score: Math.round(clamp(score, 0, 100)),
      display: display,
      missing: !!missing
    };
  }

  function buildDimension(key, label, weight, indicators) {
    var note = indicators.length
      ? Math.round(indicators.reduce(function (sum, item) { return sum + item.score; }, 0) / indicators.length)
      : 0;
    return {
      key: key,
      label: label,
      weight: weight,
      note: note,
      contribution: Math.round((weight * note / 100) * 100) / 100,
      indicators: indicators
    };
  }

  function buildDimensions(input, r, hasEeff) {
    var sector = SECTORS[input.sector] || SECTORS.otro;
    var defaultMissingScore = hasEeff === false ? 40 : 0;

    var liquidez = buildDimension("liquidez", "A. Liquidez y capital de trabajo", WEIGHTS.liquidez, [
      makeIndicator(
        "Razón corriente",
        r.razonCorriente,
        r.razonCorriente === null ? defaultMissingScore : scoreHigher(r.razonCorriente, [[1.5, 100], [1.2, 80], [1, 60], [0.8, 35], [0, 0]]),
        r.razonCorriente === null ? "Sin balance" : formatRatio(r.razonCorriente) + "x",
        r.razonCorriente === null
      ),
      makeIndicator(
        "Prueba ácida",
        r.pruebaAcida,
        r.pruebaAcida === null ? defaultMissingScore : scoreHigher(r.pruebaAcida, [[1, 100], [0.8, 75], [0.6, 50], [0.4, 25], [0, 0]]),
        r.pruebaAcida === null ? "Sin balance" : formatRatio(r.pruebaAcida) + "x",
        r.pruebaAcida === null
      ),
      makeIndicator(
        "Capital de trabajo / venta mensual",
        r.capitalTrabajoRatio,
        r.capitalTrabajoRatio === null ? defaultMissingScore : r.capitalTrabajoRatio >= 1 ? 100 : r.capitalTrabajoRatio >= 0.5 ? 80 : r.capitalTrabajoRatio >= 0 ? 50 : 0,
        r.capitalTrabajoRatio === null ? "Sin balance" : formatRatio(r.capitalTrabajoRatio) + "x · " + formatCLP(r.capitalTrabajo),
        r.capitalTrabajoRatio === null
      )
    ]);

    var margenScore = r.margenEbitda === null
      ? defaultMissingScore
      : r.margenEbitda >= sector.margenBueno
        ? 100
        : r.margenEbitda >= sector.margenAceptable
          ? 80
          : r.margenEbitda > 0
            ? 50
            : 0;

    var rentabilidad = buildDimension("rentabilidad", "B. Rentabilidad y flujo de caja", WEIGHTS.rentabilidad, [
      makeIndicator("Margen EBITDA", r.margenEbitda, margenScore, r.margenEbitda === null ? "Sin balance" : formatPct(r.margenEbitda), r.margenEbitda === null),
      makeIndicator(
        "Flujo operacional / ventas",
        r.flujoMargen,
        r.flujoMargen === null ? defaultMissingScore : r.flujoMargen >= 0.1 ? 100 : r.flujoMargen >= 0.05 ? 80 : r.flujoMargen > 0 ? 60 : 0,
        r.flujoMargen === null ? "Sin balance" : formatPct(r.flujoMargen),
        r.flujoMargen === null
      ),
      makeIndicator(
        "Cobertura de intereses (EBITDA / gastos)",
        r.coberturaIntereses,
        r.coberturaIntereses === null ? defaultMissingScore : scoreHigher(r.coberturaIntereses, [[3, 100], [2, 80], [1.5, 60], [1, 30], [0, 0]]),
        r.coberturaIntereses === null ? "Sin dato" : formatRatio(r.coberturaIntereses) + "x",
        r.coberturaIntereses === null
      ),
      makeIndicator(
        "Cobertura de servicio de deuda (FCO / servicio)",
        r.coberturaServicio,
        r.coberturaServicio === null ? defaultMissingScore : scoreHigher(r.coberturaServicio, [[1.5, 100], [1.2, 80], [1, 60], [0.8, 30], [0, 0]]),
        r.coberturaServicio === null ? "Sin dato" : formatRatio(r.coberturaServicio) + "x",
        r.coberturaServicio === null
      )
    ]);

    var endeudamiento = buildDimension("endeudamiento", "C. Endeudamiento y solvencia", WEIGHTS.endeudamiento, [
      makeIndicator(
        "Pasivo total / patrimonio",
        r.deudaPatrimonio,
        r.deudaPatrimonio === null ? defaultMissingScore : scoreLower(r.deudaPatrimonio, [[0.8, 100], [1.5, 80], [2.5, 60], [4, 30], [Infinity, 0]]),
        r.deudaPatrimonio === null ? "Sin balance" : formatRatio(r.deudaPatrimonio) + "x",
        r.deudaPatrimonio === null
      ),
      makeIndicator(
        "Deuda neta / EBITDA",
        r.deudaNetaEbitda,
        r.deudaNetaEbitda === null ? defaultMissingScore : scoreLower(r.deudaNetaEbitda, [[1, 100], [2, 85], [3, 60], [4, 35], [Infinity, 0]]),
        r.deudaNetaEbitda === null ? "Sin balance" : formatRatio(r.deudaNetaEbitda) + "x",
        r.deudaNetaEbitda === null
      ),
      makeIndicator(
        "Caja / deuda financiera CP",
        r.cajaDeudaCP,
        r.cajaDeudaCP === null ? defaultMissingScore : scoreHigher(r.cajaDeudaCP, [[1.5, 100], [1, 80], [0.5, 50], [0, 0]]),
        r.cajaDeudaCP === null ? "Sin dato" : formatRatio(r.cajaDeudaCP) + "x",
        r.cajaDeudaCP === null
      ),
      makeIndicator(
        "Deuda financiera CP / deuda total",
        r.deudaCPShare,
        r.deudaCPShare === null ? defaultMissingScore : scoreLower(r.deudaCPShare, [[0.2, 100], [0.4, 80], [0.6, 50], [Infinity, 20]]),
        r.deudaCPShare === null ? "Sin dato" : formatPct(r.deudaCPShare),
        r.deudaCPShare === null
      )
    ]);

    var payment = PAYMENT_HISTORY[input.pagoHistorico] || PAYMENT_HISTORY.sin_historial;
    var comercialScore = 50;
    var comercialDisplay = "No disponible (puntaje neutro)";
    if (input.docs.dicom) {
      if (input.protestos === 0 && input.morosidades === 0 && input.montoMorosidades === 0) {
        comercialScore = 100;
        comercialDisplay = "Sin morosidades ni protestos";
      } else if (input.protestos === 0 && input.morosidades <= 1 && input.montoMorosidades <= 1000000) {
        comercialScore = 60;
        comercialDisplay = "Morosidad menor";
      } else {
        comercialScore = 0;
        comercialDisplay = "Morosidades o protestos relevantes";
      }
    }

    var pago = buildDimension("pago", "D. Comportamiento de pago", WEIGHTS.pago, [
      makeIndicator(
        "Mora máxima CMF",
        input.maxDiasMora,
        scoreLower(input.maxDiasMora, [[0, 100], [30, 70], [59, 40], [Infinity, 0]]),
        input.maxDiasMora + " días",
        false
      ),
      makeIndicator(
        "Deuda vencida / deuda financiera",
        r.vencidaRatio,
        scoreLower(r.vencidaRatio, [[0, 100], [0.05, 80], [0.1, 50], [Infinity, 0]]),
        formatPct(r.vencidaRatio),
        r.vencidaRatio === null
      ),
      makeIndicator(
        "Historial de pago con la empresa",
        payment.score,
        payment.score,
        payment.label,
        false
      ),
      makeIndicator(
        "Facturas vencidas / venta mensual",
        r.facturasVencidasRatio,
        scoreLower(r.facturasVencidasRatio, [[0, 100], [0.05, 80], [0.1, 50], [Infinity, 0]]),
        formatPct(r.facturasVencidasRatio),
        r.facturasVencidasRatio === null
      ),
      makeIndicator(
        "Antecedentes comerciales (DICOM)",
        comercialScore,
        comercialScore,
        comercialDisplay,
        false
      )
    ]);

    var trend = input.tendenciaVentas;
    var trendLabel = trend === "sube" ? "Al alza" : trend === "estable" ? "Estable" : trend === "cae" ? "A la baja" : "No informada";
    var trendScore = trend === "sube" ? 100 : trend === "estable" ? 80 : trend === "cae" ? 30 : 50;
    var docsOk = REQUIRED_DOCS.filter(function (key) { return input.docs[key]; }).length;
    var docsScore = docsOk === REQUIRED_DOCS.length ? 100 : docsOk >= 3 ? 60 : docsOk >= 1 ? 30 : 0;
    var concentration = input.concentracionTopCliente;
    var concentrationScore = concentration === null ? 50 : concentration <= 20 ? 100 : concentration <= 40 ? 70 : concentration <= 60 ? 40 : 0;

    var estabilidad = buildDimension("estabilidad", "E. Estabilidad y calidad de información", WEIGHTS.estabilidad, [
      makeIndicator(
        "Antigüedad",
        input.antiguedad,
        scoreHigher(input.antiguedad, [[5, 100], [3, 80], [1, 60], [0.5, 30], [0, 0]]),
        input.antiguedad === null ? "Sin dato" : input.antiguedad + " años",
        input.antiguedad === null
      ),
      makeIndicator("Tendencia de ventas", trendScore, trendScore, trendLabel, false),
      makeIndicator("Estados financieros verificados", input.eeccVerificados ? 100 : 40, input.eeccVerificados ? 100 : 40, input.eeccVerificados ? "Sí" : "No verificados", false),
      makeIndicator("Documentación obligatoria", docsScore, docsScore, docsOk + "/" + REQUIRED_DOCS.length + " documentos", docsOk < REQUIRED_DOCS.length),
      makeIndicator("Concentración top cliente", concentrationScore, concentrationScore, concentration === null ? "No informada" : formatPct(concentration / 100), concentration === null)
    ]);

    return [liquidez, rentabilidad, endeudamiento, pago, estabilidad];
  }

  function getClassification(score) {
    if (score >= 85) return { label: "Riesgo bajo", decision: "Evaluar crédito normal", tone: "ok" };
    if (score >= 70) return { label: "Riesgo moderado-bajo", decision: "Aprobar con límite definido", tone: "ok" };
    if (score >= 55) return { label: "Riesgo medio", decision: "Reducir límite o solicitar garantías", tone: "warn" };
    if (score >= 40) return { label: "Riesgo alto", decision: "Anticipo, prepago o revisión especial", tone: "bad" };
    return { label: "Riesgo muy alto", decision: "No otorgar crédito sin mitigantes suficientes", tone: "bad" };
  }

  function resolveTerm(input, score, statusKey, hasEeff) {
    var notes = [];
    var max = statusKey === "approved" ? 60 : statusKey === "conditional" || statusKey === "review" ? 30 : 0;
    if (statusKey === "approved" && score >= 85 && input.plazo >= 90) {
      var mitigant = input.aval || input.garantia || input.seguroCredito;
      if (input.validacionLegal && input.autorizacion90 && input.justificacion90 && mitigant) {
        max = 90;
      } else {
        notes.push("90 días no habilitado: requiere validación legal, autorización superior, justificación comercial y mitigante (aval, garantía o seguro de crédito).");
      }
    }
    if (max > 30 && !input.validacionLegal) {
      max = 30;
      notes.push("Plazo superior a 30 días bloqueado por falta de validación legal (Ley 19.983).");
    }
    if (max > 60 && !input.autorizacion90) {
      max = 60;
      notes.push("Plazo de 90 días bloqueado por falta de autorización superior.");
    }
    if (hasEeff === false && max > 30) {
      max = 30;
      notes.push("Plazo restringido a 30 días como máximo por ausencia de Estados Financieros / Balance auditado.");
    }
    var requested = input.plazo > 0 ? input.plazo : max;
    var approved = Math.min(requested, max);
    if (max > 0 && approved < requested) {
      notes.push("Plazo solicitado de " + requested + " días reducido a " + approved + " días según política.");
    }
    return { requested: requested, max: max, approved: approved, notes: notes };
  }

  function computeLimits(input, term, statusKey, r, hasEeff, score) {
    var factor = clamp(input.factorComercial, 0.1, 1.5);
    var multiplier = clamp(input.multiplicadorFlujo, 0.1, 10);
    var commercial = input.ventas12m > 0 && term.approved > 0
      ? (input.ventas12m / 365) * term.approved * factor
      : 0;

    var financial = 0;
    var isEeffPenalized = false;
    var eeffHaircut = 1.0;

    if (hasEeff === false) {
      // Sin EE.FF. ni balance: se calcula capacidad sobre ventas mensuales (Carpeta Tributaria F29) castigada al 50%
      isEeffPenalized = true;
      eeffHaircut = 0.50;
      var ventaMensualF29 = input.ventas12m > 0 ? input.ventas12m / 12 : 0;
      // Capacidad estimada sobre flujo operacional tributario con haircut del 50%
      financial = ventaMensualF29 * 0.50 * factor;
    } else {
      // Con EE.FF.: si el EBITDA es nulo o negativo, no hay capacidad financiera ordinaria
      if (input.ebitda !== null && input.ebitda > 0 && r.flujoLibre !== null && r.flujoLibre > 0) {
        financial = Math.max(0, r.flujoLibre) * multiplier;
      }
    }

    // ESTIMACIÓN DINÁMICA DEL LÍMITE DE POLÍTICA DE RIESGO (OPCIÓN 3)
    // Combina solvencia patrimonial (10% a 20%) y rotación comercial (8% a 15% de ventas anuales),
    // ponderado dinámicamente según el score crediticio obtenido.
    var isRiskEstimated = false;
    var risk = 0;
    if (input.limitePoliticaRiesgo !== null && input.limitePoliticaRiesgo > 0) {
      risk = input.limitePoliticaRiesgo;
    } else {
      isRiskEstimated = true;
      var scoreVal = typeof score === "number" ? score : 60;
      // Coeficiente según score: de 0.10 (score <= 50) a 0.20 (score >= 85) para patrimonio
      var patPct = clamp(0.10 + (Math.max(0, scoreVal - 50) / 35) * 0.10, 0.08, 0.20);
      // Coeficiente sobre ventas anuales: de 0.08 a 0.15 (aprox 1.0 a 1.8 meses de venta)
      var vtaPct = clamp(0.08 + (Math.max(0, scoreVal - 50) / 35) * 0.07, 0.06, 0.15);

      var cupoPatrimonio = (input.patrimonio !== null && input.patrimonio > 0) ? input.patrimonio * patPct : null;
      var cupoVentas = (input.ventas12m !== null && input.ventas12m > 0) ? input.ventas12m * vtaPct : null;

      if (cupoPatrimonio !== null && cupoVentas !== null) {
        // Enfoque prudencial combinado: promedio armónico/mínimo ponderado
        // Si el patrimonio es sólido pero ventas bajas, las ventas acotan; si ventas altas pero poco patrimonio, el patrimonio acota.
        risk = Math.min(cupoPatrimonio, cupoVentas * 1.25);
      } else if (cupoPatrimonio !== null) {
        risk = cupoPatrimonio;
      } else if (cupoVentas !== null) {
        risk = cupoVentas * (hasEeff ? 1.0 : 0.65); // Haircut si no hay balance patrimonial
      } else {
        risk = 15000000; // Piso base de política general para pymes activas
      }
      risk = Math.max(1000000, Math.round(risk / 500000) * 500000);
    }

    var gross = Math.min(commercial, financial, risk);
    var limitingFactor = commercial <= financial && commercial <= risk ? "commercial" : financial <= risk ? "financial" : "risk";

    if (isEeffPenalized) {
      // Aplicación explícita del castigo del 50% por falta de balances
      gross = gross * eeffHaircut;
    }

    if (statusKey === "review") {
      var mitigant = input.aval || input.garantia || input.seguroCredito;
      gross = gross * (mitigant ? 0.85 : 0.7);
    }
    if (["no_ordinary", "rejected", "blocked"].indexOf(statusKey) >= 0) {
      gross = 0;
      limitingFactor = "policy";
    }
    var exposure = Math.max(0, input.exposicionActual);
    var available = Math.max(0, gross - exposure);
    var requested = input.montoSolicitado > 0 ? input.montoSolicitado : available;
    var approved = statusKey === "pending" ? 0 : Math.min(requested, available);
    approved = Math.floor(approved / 100000) * 100000;
    if (approved < 500000) approved = 0;
    return {
      commercial: commercial,
      financial: financial,
      risk: risk,
      gross: gross,
      exposure: exposure,
      available: available,
      requested: requested,
      approved: approved,
      limitingFactor: limitingFactor,
      factor: factor,
      multiplier: multiplier,
      termDays: term.approved,
      isEeffPenalized: isEeffPenalized,
      eeffHaircut: eeffHaircut,
      isRiskEstimated: isRiskEstimated
    };
  }

  function evaluate(raw) {
    var input = normalize(raw);
    var hasEeff = Boolean(
      (input.docs && input.docs.eecc) ||
      (input.activoCorriente !== null && input.pasivoTotal !== null && input.ebitda !== null)
    );
    var r = ratios(input);
    var dimensions = buildDimensions(input, r, hasEeff);
    var score = Math.round(dimensions.reduce(function (sum, dim) {
      return sum + dim.weight * dim.note / 100;
    }, 0) * 10) / 10;
    var classification = getClassification(score);
    var issues = [];

    function add(severity, text, critical) {
      issues.push({ severity: severity, text: text, critical: !!critical });
    }

    if (!input.rut) add("pending", "RUT de la empresa no informado.");
    else if (!isValidRut(input.rut)) add("hard", "RUT de la empresa inválido.");
    if (!input.rutERut) add("pending", "RUT del e-RUT no informado.");
    else if (input.rut && input.rutERut !== input.rut) {
      add("hard", "El RUT del e-RUT (" + formatRut(input.rutERut) + ") no coincide con el RUT de la empresa (" + formatRut(input.rut) + ").");
    }
    if (!input.rutSolicitante) add("pending", "RUT del solicitante no informado.");
    else if (!isValidRut(input.rutSolicitante)) add("hard", "RUT del solicitante inválido.");
    if (!input.representantes.length) add("pending", "Nómina de representantes legales no informada.");
    else if (isValidRut(input.rutSolicitante) && input.representantes.indexOf(input.rutSolicitante) < 0) {
      add("hard", "El solicitante no figura en la nómina de representantes legales del e-RUT.");
    }
    if (!input.inicioVigente) add("hard", "Inicio de actividades no vigente o término de giro.");
    if (!input.sociedadVigente) add("hard", "Sociedad sin vigencia según certificado.");
    if (!input.facultades) add("hard", "Representante sin facultades suficientes para obligar o endeudar a la sociedad.");

    if (input.antiguedad === null) add("pending", "Antigüedad de la empresa no informada.");
    if (input.ventas12m === null) add("pending", "Ventas de los últimos 12 meses no informadas.");
    else if (input.ventas12m <= 0) add("hard", "Sin ventas formales en los últimos 12 meses.");

    var requiredFinancial = [
      ["activoCorriente", "Activo corriente"],
      ["pasivoCorriente", "Pasivo corriente"],
      ["ebitda", "EBITDA"],
      ["flujoCajaOperacional", "Flujo de caja operacional"],
      ["pasivoTotal", "Pasivo total"],
      ["patrimonio", "Patrimonio"],
      ["deudaFinanciera", "Deuda financiera total"]
    ];

    if (hasEeff) {
      requiredFinancial.forEach(function (item) {
        if (input[item[0]] === null) add("pending", "Falta " + item[1] + ".");
      });
    } else {
      // Cliente sin balances ni estados financieros
      add(
        "warning",
        "Sin Estados Financieros / Balance: se aplica castigo del 50% sobre capacidad calculada y plazo máximo de 30 días (evaluado con flujo F29 SII).",
        false
      );
    }

    REQUIRED_DOCS.forEach(function (key) {
      if (key === "eecc" && !hasEeff) {
        // En evaluación tributaria sin balance, no bloquear como pending general
        return;
      }
      if (!input.docs[key]) add("pending", "Documento pendiente: " + DOC_LABELS[key] + ".");
    });
    if (!input.docs.dicom) add("info", "DICOM no disponible: se aplicó puntaje neutro y se recomienda validar antecedentes comerciales.");

    if (input.patrimonio !== null && input.patrimonio <= 0) add("hard", "Patrimonio negativo o nulo: señal de insolvencia.");
    if (input.deudaCastigada > 0) add("hard", "Deuda castigada en el sistema financiero (" + formatCLP(input.deudaCastigada) + ").");
    if (input.maxDiasMora >= 60) add("hard", "Mora financiera crítica: " + input.maxDiasMora + " días (máximo tolerable: menos de 60 días).");
    else if (input.maxDiasMora >= 30) add("warning", "Mora financiera relevante: " + input.maxDiasMora + " días.", true);
    else if (input.maxDiasMora > 0) add("warning", "Mora financiera de " + input.maxDiasMora + " días.");
    if (input.protestos > 0) add("hard", "Registra " + input.protestos + " protesto(s) comercial(es) vigente(s).");
    if (input.montoMorosidades > 2500000) add("hard", "Morosidades comerciales superiores a $2.500.000 (" + formatCLP(input.montoMorosidades) + ").");
    else if (input.montoMorosidades > 0 || input.morosidades > 0) add("warning", "Morosidades comerciales informadas: " + input.morosidades + " registro(s), " + formatCLP(input.montoMorosidades) + ".");
    if (input.deudaVencida > 0) {
      var overdueCritical = r.ventasMensuales !== null && r.ventasMensuales > 0 && input.deudaVencida > r.ventasMensuales * 0.05;
      add("warning", "Deuda financiera vencida: " + formatCLP(input.deudaVencida) + ".", overdueCritical);
    }
    if (input.f29SinDeclarar >= 3) add("hard", "Desorden tributario severo: " + input.f29SinDeclarar + " períodos F29 sin declarar.");
    else if (input.f29SinDeclarar > 0) add("warning", input.f29SinDeclarar + " período(s) F29 sin declarar o con pago pendiente.");
    if (input.deudaTGR > 0) {
      if (r.ventasMensuales !== null && r.ventasMensuales > 0 && input.deudaTGR > r.ventasMensuales * 0.35 && input.deudaTGR > 2000000) {
        add("hard", "Deuda TGR (" + formatCLP(input.deudaTGR) + ") supera el 35% de la venta mensual y $2.000.000.");
      } else {
        add("warning", "Deuda fiscal en TGR: " + formatCLP(input.deudaTGR) + ".");
      }
    }
    if (input.situacionTributaria === "esp") add("warning", "Atrasos tributarios esporádicos informados.");
    if (input.situacionTributaria === "deu" && input.deudaTGR === 0) add("warning", "Situación tributaria con deuda declarada, pero sin monto TGR informado.");
    if (input.instituciones >= 5) add("warning", "Alta dispersión de acreedores: " + input.instituciones + " instituciones financieras.");
    if (input.tendenciaVentas === "cae") add("warning", "Tendencia de ventas a la baja en el período evaluado.");
    if (!input.eeccVerificados) add("warning", "Estados financieros no verificados o sin documentación de respaldo.");
    if (input.concentracionTopCliente !== null && input.concentracionTopCliente > 50) {
      add("warning", "Alta concentración de ventas en un cliente: " + formatPct(input.concentracionTopCliente / 100) + ".", input.concentracionTopCliente > 80);
    }
    if (r.dso !== null && r.dso > 120) {
      add("warning", "DSO muy elevado: " + Math.round(r.dso) + " días de cobro. Revisa la calidad de las cuentas por cobrar.", true);
    } else if (r.dso !== null && r.dso > 90) {
      add("warning", "DSO elevado: " + Math.round(r.dso) + " días de cobro.");
    }
    if (input.pagoHistorico === "atraso_moderado") add("warning", "Historial de pago con atrasos moderados con la empresa.", true);
    if (input.pagoHistorico === "atraso_grave") add("warning", "Historial de pago con atrasos graves con la empresa.", true);
    if (input.pagoHistorico === "sin_historial") add("info", "Sin historial de pago con la empresa: se aplicó puntaje neutro.");
    if (r.flujoLibre !== null && r.flujoLibre <= 0) {
      add("warning", input.servicioDeuda > 0
        ? "Flujo libre insuficiente: el flujo operacional no cubre el servicio de deuda."
        : "Flujo libre nulo o negativo tras cubrir la operación.", true);
    }
    if (input.ebitda !== null && input.ebitda <= 0 && input.flujoCajaOperacional !== null && input.flujoCajaOperacional <= 0) {
      add("warning", "EBITDA y flujo operacional negativos: señal de deterioro.", true);
    }
    if (input.limitePoliticaRiesgo !== null && input.exposicionActual >= input.limitePoliticaRiesgo) {
      add("warning", "La exposición actual alcanza o supera el límite de política de riesgo por cliente.", true);
    }
    if (input.deudaFinanciera > 0 && (input.servicioDeuda === 0 || input.servicioDeuda === null)) add("pending", "Servicio de deuda no informado pese a deuda financiera vigente.");
    if (input.deudaFinanciera > 0 && (input.gastosFinancieros === 0 || input.gastosFinancieros === null)) add("pending", "Gastos financieros no informados pese a deuda financiera vigente.");
    if (input.pasivoCorriente !== null && input.activoCorriente !== null && input.pasivoCorriente > input.activoCorriente) {
      add("warning", "Pasivo corriente supera al activo corriente: capital de trabajo negativo.");
    }
    if (input.deudaFinancieraCP !== null && input.deudaFinanciera !== null && input.deudaFinancieraCP > input.deudaFinanciera) {
      add("warning", "Deuda financiera de corto plazo supera la deuda financiera total: revisa datos.");
    }
    if (input.pasivoTotal !== null && input.patrimonio !== null && input.patrimonio > 0 && input.pasivoTotal > input.patrimonio * 4) {
      add("warning", "Apalancamiento contable superior a 4 veces el patrimonio.");
    }
    if (input.montoMorosidades > 0 && input.morosidades === 0) add("warning", "Monto de morosidades informado sin número de registros: revisa DICOM.");
    if (input.deudaSociosRelacionados !== null && input.deudaSociosRelacionados > 0) {
      add("warning", "Deuda con socios o relacionados (" + formatCLP(input.deudaSociosRelacionados) + "): evaluar como deuda subordinada o vinculada en el análisis.");
    }
    if (input.diferenciaCambio !== null && input.diferenciaCambio < 0) {
      add("warning", "Diferencia de cambio neta desfavorable (" + formatCLP(Math.abs(input.diferenciaCambio)) + "): exposición cambiaria relevante (no incluida en gastos financieros).");
    }

    var hasHard = issues.some(function (item) { return item.severity === "hard"; });
    var hasPending = issues.some(function (item) { return item.severity === "pending"; });
    var hasCriticalWarning = issues.some(function (item) { return item.severity === "warning" && item.critical; });
    var status;
    if (hasHard) status = Object.assign({}, STATUS.blocked);
    else if (hasPending) status = Object.assign({}, STATUS.pending);
    else if (score >= 85) status = Object.assign({}, hasCriticalWarning ? STATUS.review : STATUS.approved);
    else if (score >= 70) status = Object.assign({}, hasCriticalWarning ? STATUS.review : STATUS.conditional);
    else if (score >= 55) status = Object.assign({}, STATUS.review);
    else if (score >= 40) status = Object.assign({}, STATUS.no_ordinary);
    else status = Object.assign({}, STATUS.rejected);

    var term = resolveTerm(input, score, status.key, hasEeff);
    var limits = computeLimits(input, term, status.key, r, hasEeff, score);

    if (limits.available > 0 && limits.available < 500000 && ["approved", "conditional", "review"].indexOf(status.key) >= 0) {
      add("warning", "Disponibilidad adicional inferior al mínimo operacional (" + formatCLP(500000) + ").");
    }
    if (input.montoSolicitado > 0 && input.montoSolicitado < 500000 && ["approved", "conditional", "review"].indexOf(status.key) >= 0) {
      add("warning", "Monto solicitado inferior al mínimo operacional (" + formatCLP(500000) + ").");
    }
    if (limits.available > 0 && limits.requested > limits.available && ["approved", "conditional", "review"].indexOf(status.key) >= 0) {
      add("info", "El monto solicitado (" + formatCLP(limits.requested) + ") supera la disponibilidad (" + formatCLP(limits.available) + ").");
    }
    if (limits.available === 0 && limits.exposure > 0 && ["approved", "conditional", "review"].indexOf(status.key) >= 0) {
      add("warning", "Sin disponibilidad adicional: la exposición actual (" + formatCLP(limits.exposure) + ") alcanza o supera el límite bruto.", true);
    }
    var finalStatus = status;
    if (limits.approved === 0 && ["approved", "conditional", "review"].indexOf(status.key) >= 0) {
      if (limits.gross > 0 && limits.available === 0) {
        finalStatus = Object.assign({}, STATUS.no_availability);
      } else {
        if (limits.gross === 0) {
          add("warning", "El límite calculado es cero: no hay capacidad de crédito con los antecedentes actuales.", true);
        }
        finalStatus = Object.assign({}, STATUS.review);
      }
      term.approved = 0;
      term.notes.push("Plazo no habilitado mientras no exista disponibilidad o capacidad de crédito.");
    }

    if (["approved", "conditional", "review", "no_availability"].indexOf(finalStatus.key) >= 0) {
      if (limits.limitingFactor === "commercial") add("info", "El límite comercial (ventas y plazo) es el factor restrictivo.");
      if (limits.limitingFactor === "financial") add("info", "El límite financiero (flujo de caja) es el factor restrictivo.");
      if (limits.limitingFactor === "risk") add("info", "El límite de política de riesgo por cliente es el factor restrictivo.");
    }

    var rank = { hard: 0, pending: 1, warning: 2, info: 3 };
    issues.sort(function (a, b) {
      if (a.severity === "warning" && b.severity === "warning" && a.critical !== b.critical) return a.critical ? -1 : 1;
      return rank[a.severity] - rank[b.severity];
    });

    return {
      input: input,
      ratios: r,
      dimensions: dimensions,
      score: score,
      scoreDisplay: Math.round(score),
      classification: classification,
      status: finalStatus,
      term: term,
      limits: limits,
      issues: issues,
      hardBlockers: issues.filter(function (item) { return item.severity === "hard"; }),
      pendingItems: issues.filter(function (item) { return item.severity === "pending"; }),
      warnings: issues.filter(function (item) { return item.severity === "warning"; }),
      infoItems: issues.filter(function (item) { return item.severity === "info"; }),
      generatedAt: new Date().toISOString(),
      prediction: (function () {
        try {
          var ml = (typeof globalThis !== "undefined" && globalThis.CreditML) ? globalThis.CreditML
            : (typeof window !== "undefined" && window.CreditML) ? window.CreditML : null;
          if (ml && typeof ml.predict === "function") return ml.predict(raw);
        } catch (e) {}
        return null;
      })()
    };
  }

  return {
    evaluate: evaluate,
    normalize: normalize,
    ratios: ratios,
    cleanRut: cleanRut,
    isValidRut: isValidRut,
    formatRut: formatRut,
    parseRutList: parseRutList,
    formatCLP: formatCLP,
    formatPct: formatPct,
    formatRatio: formatRatio,
    SECTORS: SECTORS,
    WEIGHTS: WEIGHTS,
    PAYMENT_HISTORY: PAYMENT_HISTORY,
    STATUS: STATUS,
    REQUIRED_DOCS: REQUIRED_DOCS,
    DOC_LABELS: DOC_LABELS
  };
});
