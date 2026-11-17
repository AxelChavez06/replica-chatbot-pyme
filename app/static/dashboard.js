(() => {
  const $ = (id) => document.getElementById(id);
  const fmt = (v, d = 1) => (v === null || v === undefined ? "—" : Number(v).toFixed(d));

  function kpi(container, items) {
    container.textContent = "";
    items.forEach(([label, value, note]) => {
      const d = document.createElement("div");
      d.className = "kpi";
      const l = document.createElement("div"); l.className = "kpi__label"; l.textContent = label;
      const v = document.createElement("div"); v.className = "kpi__value"; v.textContent = value;
      d.append(l, v);
      if (note) { const n = document.createElement("div"); n.className = "kpi__note"; n.textContent = note; d.appendChild(n); }
      container.appendChild(d);
    });
  }

  function fill(tbody, rows) {
    tbody.textContent = "";
    rows.forEach((cells) => {
      const tr = document.createElement("tr");
      cells.forEach((c) => { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
      tbody.appendChild(tr);
    });
  }

  async function loadStatic() {
    const d = await (await fetch("/api/experiment")).json();
    const p = d.paper;
    kpi($("paper-kpis"), [
      ["Tiempo de respuesta", `${fmt(p.tiempo_respuesta_min.antes, 2)} → ${fmt(p.tiempo_respuesta_min.despues, 2)} min`, "promedio antes → después (humano + bot)"],
      ["Satisfacción (1–5)", `${fmt(p.satisfaccion.antes, 2)} → ${fmt(p.satisfaccion.despues, 2)}`, "encuesta a clientes reales"],
      ["Atendidas por chatbot", `${fmt(p.pct_atendidas_chatbot_prom_feb_abr, 1)}%`, "promedio feb–abr 2025"],
      ["Consultas por mes", `${fmt(p.consultas_mes.antes, 1)} → ${fmt(p.consultas_mes.despues, 1)}`, "promedio antes → después"],
    ]);
    const e = d.experiment;
    $("exp-missing").hidden = !!e;
    if (e) {
      $("n-q").textContent = e.n_consultas;
      const r = e.resultados, c = e.clasificacion, l = e.latencia_ms;
      kpi($("exp-kpis"), [
        ["Exactitud de intenciones", `${fmt(c.exactitud_intenciones * 100)}%`, `${e.n_con_intencion_real} consultas con intención real · macro-F1 ${fmt(c.macro_f1, 3)}`],
        ["Resueltas automáticamente", `${fmt(r.pct_resueltas_automaticamente)}%`, `+ ${fmt(r.pct_aclaracion)}% piden aclaración`],
        ["Derivadas a humano", `${fmt(r.pct_derivadas)}%`, `umbral de confianza ${e.umbral_confianza}`],
        ["Exactitud de enrutamiento", `${fmt(r.exactitud_enrutamiento_pct)}%`, "resultado del bot = resultado esperado"],
        ["Latencia (mediana / p95)", `${fmt(l.mediana, 1)} / ${fmt(l.p95, 1)} ms`, "procesamiento del servidor"],
      ]);
      fill($("tag-table").tBodies[0], e.por_etiqueta.map((t) => [
        t.tag, t.n, `${fmt(t.routing_accuracy * 100, 0)}%`, t.resuelto, t.aclaracion, t.derivado,
      ]));
    }
    fill($("cmp-table").tBodies[0], d.comparison.map((r) => [r.indicador, r.articulo, r.prototipo, r.comparable]));
  }

  async function loadLive() {
    const m = await (await fetch("/api/metrics/live")).json();
    kpi($("live-kpis"), [
      ["Consultas", m.total_consultas, "sin contar saludos"],
      ["Resueltas", m.resueltas, m.pct_resueltas === null ? "" : `${fmt(m.pct_resueltas)}%`],
      ["Derivadas", m.derivadas, m.pct_derivadas === null ? "" : `${fmt(m.pct_derivadas)}%`],
      ["Latencia media", m.latencia_ms_media === null ? "—" : `${fmt(m.latencia_ms_media, 1)} ms`, m.nota],
    ]);
    const q = await (await fetch("/api/operator-queue")).json();
    fill($("queue-table").tBodies[0], q.map((r) => [`#${r.id}`, r.created_at.slice(11), r.reason, r.user_message]));
  }

  loadStatic();
  loadLive();
  setInterval(loadLive, 5000);
})();
