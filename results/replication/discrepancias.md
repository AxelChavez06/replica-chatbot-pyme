# Discrepancias entre la réplica y el artículo

Generado automáticamente por `python -m analysis.replicate`.

## 1. Cifras que SÍ coinciden

- Tabla 1: porcentajes de consultas atendidas por chatbot recalculados = publicados: **True**.
- Tabla 1: atendidas por chatbot + derivadas = total en los 7 meses: **True**.
- Tabla 2: promedios antes/después recalculados = publicados: **True**.
- Tabla 2: cambios porcentuales recalculados = publicados: **True**.
- Tabla 2: 74.20% atendido por chatbot se reproduce como promedio de los porcentajes mensuales (74.2%). El cálculo agrupado (suma/suma) da 74.27%, por lo que el artículo usó el promedio de porcentajes.
- Tablas 3 y 4: los porcentajes publicados coinciden con n / suma(n) (ver CSV).

## 2. Pruebas de Mann-Whitney U (H1-H3)

Con las cifras mensuales de la Tabla 1 (n=4 pre, n=3 post):

| Hipótesis              | Tipo de hipótesis   | n pre / n post   |   U (post vs pre) |   Rank-biserial (post vs pre) |   p exacto bilateral (permutación, con empates) |   p exacto bilateral (scipy, ignora empates) |   p exacto en la dirección de la hipótesis |   p asintótico bilateral (con corrección de continuidad) |   p asintótico bilateral (sin corrección) | Publicado                          | Reproduce lo publicado (exacto bilateral, α=0.05)   |
|:-----------------------|:--------------------|:-----------------|------------------:|------------------------------:|------------------------------------------------:|---------------------------------------------:|-------------------------------------------:|---------------------------------------------------------:|------------------------------------------:|:-----------------------------------|:----------------------------------------------------|
| H1 Tiempo de respuesta | reducción           | 4 / 3            |                 0 |                            -1 |                                          0.0571 |                                       0.0571 |                                     0.0286 |                                                   0.0518 |                                    0.0339 | Tabla 2: p>0.05 (no significativo) | True                                                |
| H2 Satisfacción        | aumento             | 4 / 3            |                12 |                             1 |                                          0.0286 |                                       0.0571 |                                     0.0286 |                                                   0.0497 |                                    0.0323 | Tabla 2: p<0.05 (significativo)    | True                                                |
| H3 Consultas mensuales | cambio (bilateral)  | 4 / 3            |                 0 |                            -1 |                                          0.0571 |                                       0.0571 |                                     0.0571 |                                                   0.0518 |                                    0.0339 | Tabla 2: p>0.05 (no significativo) | True                                                |

Interpretación:

- **El patrón publicado SÍ se reproduce** (solo la satisfacción es significativa a α=0.05) usando la prueba exacta bilateral por permutación que respeta los empates: H1 p=0.0571, H2 p=0.0286, H3 p=0.0571.
- Ese resultado depende de un detalle: con n=4 y n=3 solo hay C(7,3)=35 asignaciones posibles, así que sin empates el p exacto bilateral mínimo es 2/35=0.0571 (nunca <0.05). En satisfacción hay un empate (3.8 y 3.8 en el periodo pre) que vuelve asimétrica la distribución nula y deja p=1/35=0.0286. Es decir, la 'significancia' de H2 y la 'no significancia' de H1/H3 provienen de la discretización y los empates, no de una diferencia real entre los tres indicadores: **los tres** muestran separación completa entre periodos (rank-biserial = ±1).
- La función de SciPy con `method='exact'` ignora los empates y da 0.0571 en los tres (no reproduce el patrón). La aproximación normal con corrección de continuidad sí lo reproduce, por margen mínimo (p=0.0518, 0.0497 y 0.0518); sin corrección los tres dan p≈0.03. No sabemos qué variante usó Statistica 12, así que la coincidencia no confirma el procedimiento.
- H1 y H2 están formuladas como direccionales; con la prueba exacta unilateral (p=0.0286) H1 también sería significativa. Los autores no aclaran si usaron pruebas uni o bilaterales.
- Con solo 3 meses post y sin control de estacionalidad, estas pruebas tienen poca potencia y no permiten atribuir causalidad al chatbot (el propio artículo lo reconoce parcialmente).

## 3. Inconsistencias textuales del artículo

- Sec. 3.1 dice que el chatbot se lanzó en enero de 2025; la Tabla 1 y la comparación pre/post usan febrero de 2025 como primer mes con chatbot.
- Sec. 4.2 dice que la proporción de consultas del chatbot pasó 'de 61% a 85%'; la Tabla 1 da 60.80%, 76.42% y 85.37%.
- Sec. 3.2 indica entrevistas a tres empleados (2 operadores + 1 coordinador); la Sec. 4.3 habla de 'dos' entrevistas semiestructuradas.
- Sec. 3.1 describe 'bienes de consumo'; la Sec. 4 describe 'artículos de moda de nicho'.
- Sec. 4.2 afirma 'strong correlation' entre automatización y satisfacción sin reportar ningún coeficiente de correlación.

## 4. Elementos que NO se pueden reproducir con datos publicados

- Datos de logs de conversación, entrevistas y comentarios de clientes (confidenciales; solo hay conteos y citas de ejemplo).
- Porcentajes por categoría de consulta (solo se dice que las cinco categorías suman >90%).
- La plataforma comercial, su modelo NLP y los árboles de diálogo originales (no se nombran).
