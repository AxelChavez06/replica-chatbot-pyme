(() => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("input");
  const box = document.getElementById("messages");
  let sid;
  try { sid = sessionStorage.getItem("sid"); } catch (e) {}
  if (!sid) { sid = "s-" + Math.random().toString(36).slice(2, 10); try { sessionStorage.setItem("sid", sid); } catch (e) {} }

  const OUTCOME = { resuelto: "Resuelto por el bot", aclaracion: "Pide aclaración", derivado: "Derivado a operador", saludo: "Saludo" };
  const REASON = {
    solicita_humano: "El cliente pidió una persona",
    lenguaje_emocional: "Lenguaje emocional",
    accion_requiere_operador: "Acción que requiere operador",
    baja_confianza: "Confianza baja del clasificador",
    falta_dato: "Falta un dato (código o producto)",
    modulo_respuesta: "Módulo de respuesta",
    relleno_dato_pendiente: "Dato pendiente completado",
    saludo: "Saludo",
  };

  function add(who, text, cls) {
    const wrap = document.createElement("div");
    wrap.className = "msg msg--" + who;
    const b = document.createElement("div");
    b.className = "bubble" + (cls ? " " + cls : "");
    b.textContent = text;
    wrap.appendChild(b);
    box.appendChild(wrap);
    box.scrollTop = box.scrollHeight;
    return wrap;
  }

  function trace(r) {
    document.getElementById("t-intent").textContent = r.intent_label || "—";
    const pct = Math.round(r.confidence * 100);
    document.getElementById("t-meter").style.width = pct + "%";
    document.getElementById("t-conf").textContent = pct + "%";
    const o = document.getElementById("t-outcome");
    o.textContent = OUTCOME[r.outcome] || r.outcome;
    o.className = "out out--" + r.outcome;
    document.getElementById("t-reason").textContent = REASON[r.reason] || r.reason;
    document.getElementById("t-ms").textContent = r.response_ms.toFixed(1) + " ms";
  }

  async function send(text) {
    add("user", text);
    const typing = add("bot", "…", "bubble--typing");
    try {
      const resp = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, message: text }),
      });
      const data = await resp.json();
      typing.remove();
      if (!resp.ok) { add("bot", data.error || "Error del servidor.", "bubble--error"); return; }
      add("bot", data.reply, data.outcome === "derivado" ? "bubble--escalated" : "");
      trace(data);
    } catch (e) {
      typing.remove();
      add("bot", "No pude conectar con el servidor.", "bubble--error");
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const t = input.value.trim();
    if (!t) return;
    input.value = "";
    send(t);
  });
  document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => send(c.dataset.q)));
})();
