# Réplica: chatbot de atención al cliente en una microempresa

Réplica (parcial y declarada) del estudio de caso de Marcineková, Sujová y Ďurica,
*Implementing AI Chatbots in Customer Service Optimization — A Case Study in Micro-Enterprise*,
**Information 2025, 16, 1078** (`articulo_original.pdf`).

> **Aviso metodológico.** El artículo usa datos reales y confidenciales de una empresa eslovaca y una plataforma
> comercial no identificada. Aquí **no** se reproducen esos datos. El proyecto tiene tres partes separadas:
> 1. **Réplica analítica**: recalcula tablas, figuras y pruebas con las cifras publicadas.
> 2. **Prototipo**: chatbot híbrido (reglas + clasificador de intenciones) con una BD simulada.
> 3. **Pruebas sintéticas**: métricas del prototipo con consultas escritas por nosotros. **No son resultados del
>    artículo ni de clientes reales**, y no se midió satisfacción.

## El artículo original

Estudio de caso único, con métodos mixtos, en una microempresa eslovaca de e-commerce (8 empleados, moda de nicho).
Se implantó un chatbot comercial **híbrido** (árboles de diálogo + NLP para clasificar intenciones, sin LLM generativo)
integrado con la base de pedidos y con derivación a operadores. Con datos mensuales de oct 2024 a abr 2025
(4 meses sin chatbot, 3 con él) los autores reportan menos tiempo de respuesta (118.25 → 64.00 min), más satisfacción
(3.73 → 4.27 en escala 1-5) y 74.2% de consultas atendidas por el chatbot. También reportan entrevistas a empleados
y comentarios de clientes. Las pruebas Mann-Whitney U (H1-H3) indican significancia solo para la satisfacción.
Limitaciones que reconocen los autores: caso único, periodo corto y sin análisis económico.
El PDF está en `articulo_original.pdf` (licencia CC BY 4.0).

## Tecnologías

Python 3.11+ (probado en 3.12) · Flask (backend) · HTML/CSS/JavaScript sin frameworks (interfaz) · SQLite (pedidos,
productos, cupones, interacciones y cola de operadores) · scikit-learn (TF-IDF + regresión logística) ·
pandas, SciPy y matplotlib (análisis, pruebas estadísticas y gráficos) · pytest. Sin APIs de pago ni servicios externos.

## Resultados publicados frente a resultados sintéticos

| Aspecto | Artículo (publicado) | Este proyecto |
|---|---|---|
| Origen de los datos | Logs y encuestas reales de una empresa | Consultas sintéticas escritas por nosotros |
| Réplica de tablas y figuras | Tablas 1-4, Figuras 1-2 | Recalculadas **exactamente** con las cifras publicadas |
| Consultas atendidas automáticamente | 74.2% (prom. feb-abr) | 62.9% (151 consultas sintéticas) · no comparable |
| Derivadas a humano | 25.8% prom. feb-abr (14.6% en abril; el texto dice 10-15%) | 30.5% · incluye casos difíciles a propósito |
| Tiempo de respuesta | 118.25 → 64.00 min (humano + bot) | ≈2-3 ms de latencia de software · no comparable |
| Satisfacción | 3.73 → 4.27 (clientes reales) | **No medida** (no se inventan encuestas) |
| Exactitud de intenciones | No informada | 94.9% (117 consultas con intención real) |

## Instalación (Windows / VS Code)

Requiere Python 3.11 o superior.

```powershell
cd replica-chatbot-pyme
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

En VS Code: `Ctrl+Shift+P` → *Python: Select Interpreter* → `.venv`.

## Ejecución

| Qué | Comando |
|---|---|
| Crear BD demo y entrenar clasificador | `python -m scripts.init_db` |
| Réplica analítica (tablas, figuras, test) | `python -m analysis.replicate` |
| Experimento con consultas sintéticas | `python -m experiments.run_experiment` |
| Aplicación web (http://127.0.0.1:5000) | `python run.py` |
| Pruebas automatizadas | `python -m pytest` |

Si PowerShell bloquea la activación del entorno, usa directamente `.\.venv\Scripts\python.exe` en vez de `python`.

Páginas: `/` (chat con traza de la decisión) y `/dashboard` (indicadores del artículo, del prototipo,
comparación y demo en vivo).

## Estructura

```
analysis/       paper_data.py (cifras publicadas) y replicate.py (tablas, figuras, Mann-Whitney)
app/            Flask: db.py (SQLite), nlu.py (clasificador), chatbot.py (motor híbrido), routes.py, templates/, static/
data/            demo.db, intents_train.txt (entrenamiento), eval_queries.txt (evaluación sintética)
experiments/    run_experiment.py
results/         replication/ (CSV, PNG, discrepancias.md) y experiment/ (metrics.json, per_query.csv, PNG)
tests/           pytest
```

## Metodología

### 1. Réplica analítica (`analysis/`)
Solo se usan números impresos en el PDF (Tablas 1-4, Figura 1). Se recalculan promedios, cambios porcentuales,
porcentajes, Figuras 1 y 2, y las pruebas de Mann-Whitney U (pre = oct-ene, n=4; post = feb-abr, n=3).
El informe `results/replication/discrepancias.md` se genera automáticamente.

### 2. Prototipo (`app/`)
Arquitectura descrita en el artículo (sec. 3.1): escenarios predefinidos + NLP para clasificar la intención,
integración con la BD de pedidos, escalamiento a humano, sin LLM generativo.

1. Saludos → respuesta fija (no cuentan como consulta).
2. Reglas de derivación: pide un humano, lenguaje emocional, acciones que requiere un operador
   (reenviar/corregir factura, cancelar pedido).
3. Clasificador de intenciones (TF-IDF de palabras y caracteres + regresión logística) sobre **las cinco categorías
   originales**: estado de pedido, disponibilidad, devoluciones, pagos, descuentos.
4. Confianza < 0.50 → derivación (`baja_confianza`).
5. Módulo de respuesta por intención, con consultas SQLite (pedidos, productos, cupones). Si falta un dato
   (código de pedido, producto) pide aclaración y recuerda la intención para el siguiente mensaje.

Cada derivación crea un ticket en `operator_queue`; cada interacción se guarda en `interactions`.

### 3. Experimento sintético (`experiments/`)
- Entrenamiento: `data/intents_train.txt` (≈150 frases escritas a mano).
- Evaluación: `data/eval_queries.txt` (151 consultas distintas de las de entrenamiento, con etiquetas:
  estándar, con ruido/errores, falta de dato, requiere operador, emocional, pide humano, fuera de alcance, ambigua).
  Incluye casos difíciles a propósito; **su composición la decidimos nosotros**, por lo que los porcentajes
  no se pueden comparar directamente con los del artículo.
- Métricas: exactitud de intenciones (117 consultas con intención real), % resueltas / aclaración / derivadas,
  exactitud de enrutamiento (resultado del bot = resultado esperado definido por nosotros), latencia de
  procesamiento del servidor (5 repeticiones, excluye el registro en BD y la red).
- Semilla fija (42). Los resultados son reproducibles salvo la latencia, que depende de la máquina.

## Resultados (última ejecución)

**Del artículo (réplica exacta):** tiempo de respuesta 118.25 → 64.00 min (−45.88%); satisfacción 3.73 → 4.27
(+14.54%); consultas/mes 685.25 → 584.33 (−14.73%); 74.20% atendido por el chatbot.

**Del prototipo (sintéticas, n=151):**

| Métrica | Valor |
|---|---|
| Exactitud de intenciones (117 consultas con intención real) | 94.9% (macro-F1 0.951) |
| Resueltas automáticamente | 62.9% |
| Piden aclaración | 6.6% |
| Derivadas a humano | 30.5% |
| Exactitud de enrutamiento | 92.7% |
| Latencia de procesamiento (mediana / p95) | ≈2–3 ms / ≈4–10 ms (varía por equipo) |

Los valores exactos están en `results/experiment/metrics.json`.

### Historial honesto del desarrollo
- Primera ejecución (umbral 0.50 fijado a priori, sin enmascarar el código de pedido): exactitud 94.9%, resueltas 62.3%,
  derivadas 31.1%, enrutamiento 92.1%.
- Luego se enmascaró el código de pedido (`PED-xxxx`) antes de clasificar (mejora general de preprocesamiento).
  Resultado actual: 94.9 / 62.9 / 30.5 / 92.7. El umbral **no** se ajustó con los resultados;
  `results/experiment/sensibilidad_umbral.csv` muestra cómo cambia con 0.3–0.7 (exploratorio).
- Como se vieron los errores de la primera ejecución antes del segundo cambio, el conjunto sintético **no es un
  test completamente ciego**. Tómalo como una demostración del comportamiento, no como una estimación de rendimiento real.
- Limitación observada: las probabilidades del clasificador son poco extremas (muchas consultas correctas
  tienen confianza 0.4-0.6), por lo que el umbral 0.50 deriva algunas consultas que sí podría resolver.
  Algunas consultas fuera de alcance o vagas ("tengo un problema", "prenda a medida") se resuelven con un módulo en vez de derivarse.

## Qué se replicó exactamente y qué es aproximación

**Exacto (con datos publicados):** Tabla 1 (porcentajes recalculados), Tabla 2 (promedios, cambios % y
74.20% como promedio de porcentajes mensuales), Tablas 3 y 4 (porcentajes), Figuras 1 y 2, pruebas Mann-Whitney.
Con la prueba **exacta bilateral por permutación que respeta empates** se reproduce el patrón publicado
(solo satisfacción con p<0.05: H1 0.0571, H2 0.0286, H3 0.0571). Ese patrón se debe a la discretización
(n=4/3) y a un empate en satisfacción: los tres indicadores tienen separación completa entre periodos.
Detalles y otras variantes de la prueba en `results/replication/discrepancias.md`.

**Aproximación:** arquitectura híbrida (reglas + NLP, sin LLM) pero con otro algoritmo, otro idioma (español, no eslovaco),
otro catálogo (moda de nicho simulado, 8 modelos), otra BD (30 pedidos ficticios), políticas ficticias (plazo de
devolución de 14 días, cupones, métodos de pago), reglas de derivación inferidas de la descripción cualitativa
(sec. 4.4) y consultas sintéticas en lugar de logs reales.

**No replicable:** datos reales (logs, entrevistas, comentarios), plataforma comercial y sus árboles de diálogo,
satisfacción de clientes, tiempos de respuesta humanos, porcentajes por categoría, análisis temático y de sentimiento
a partir de transcripciones (solo se reproducen los conteos publicados).

## Notas
- Los precios usan «S/» solo como símbolo de ejemplo; todo el catálogo, los pedidos y las políticas son ficticios.
- La fecha «de hoy» de la demo está fija en 2025-04-30 (`config.py`) para que los resultados sean deterministas.
- No se usan APIs de pago ni servicios externos.
