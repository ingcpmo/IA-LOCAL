# Palanca A — Estimación real de GPU (investigación, sin ejecutar nada)

**Estado**: investigación solicitada por Cesar tras elegir Palanca A
como dirección inicial (`docs_plan/PAQUETE_DECISION_ESTRATEGICA.md`).
Ninguna acción de infraestructura tomada — ni solicitud de cuota, ni
creación de instancia, ni gasto real.

## Hallazgo real que cambia el planteamiento original

El paquete estratégico hablaba de "GPU local". Verificado en esta
sesión: `ivr-ia` **es una VM de Google Compute Engine**
(`hotel-bot-project-492723`, zona `us-east1-b`), no hardware físico —
8 vCPU, 31GB RAM, sin GPU adjunta hoy (confirmado: `nvidia-smi` no
existe, `lspci` no muestra GPU). "Palanca A" no es instalar una tarjeta
en un servidor propio — es **adjuntar una GPU cloud a esta VM (o crear
una VM hermana con GPU)** dentro del mismo proyecto GCP.

## Requisito de VRAM (Llama 3.1 70B, cuantizado 4-bit — el candidato más citado en el proyecto)

- Mínimo real para cargar el checkpoint: **~35GB**.
- Con KV cache y margen operativo: **42-45GB** cómodos.
- A contexto largo (128K) el KV cache solo puede llegar a ~40GB
  adicionales — pero el uso real de este proyecto son chunks de hasta
  6000 caracteres (~1500-2000 tokens), muy lejos de ese extremo — el
  contexto real necesario es mucho más chico que el caso peor citado en
  la literatura.

**Conclusión de VRAM**: se necesita una GPU con **80GB** para tener
margen cómodo. 40GB queda justo/riesgoso. Una sola GPU de 24GB (ej. L4)
no alcanza para este modelo sin partirlo en 2+ GPUs.

## Opciones reales en GCP (precio de lista, on-demand, sujeto a
variación por región/descuento — verificar en la consola antes de
decidir)

| GPU | VRAM | Precio on-demand aprox. | Sirve para 70B solo |
|---|---|---|---|
| L4 | 24GB | ~$0.70/hr | No (insuficiente sola) |
| A100 40GB | 40GB | ~$3.67/hr | Riesgoso, sin margen |
| **A100 80GB** | 80GB | ~$5.03/hr | **Sí, con margen cómodo** |
| H100 | 80GB | ~$9.80-11/hr | Sí, pero sobredimensionado para este volumen |

**Recomendación de instrumento, no de decisión final**: A100 80GB es el
punto correcto — cubre el modelo con margen, sin pagar la prima de H100
(pensado para entrenamiento/lotes masivos, no para este volumen de
llamadas).

## Estimación de costo real para el uso concreto de este proyecto

El patrón de uso del analizador es por **lotes** (correr el fixture o
un corpus de documentos, no un servicio conversacional siempre
encendido) — el modelo de costo correcto es **instancia efímera**
(encender → correr el lote → apagar), no hosting 24/7.

- **Calibración contra el fixture 7P+2N** (9 llamadas — el paso
  obligatorio antes de cualquier uso real, mismo criterio ya usado para
  el modelo actual): sesión de GPU de menos de 1 hora. **Costo estimado:
  bajo $10.**
- **Corpus formal completo** (232 llamadas, presupuesto ya propuesto en
  el proyecto como `D4-2026-004`, sin confirmar): con un modelo de 70B
  en GPU real la inferencia es previsiblemente MÁS RÁPIDA por llamada
  que el 7B actual en CPU (los tiempos reales medidos en esta sesión
  fueron de 7-10 minutos por llamada en CPU — una GPU real con un modelo
  más grande pero bien servido normalmente corre en segundos a pocos
  minutos por llamada, aunque esto es una expectativa, no una medición:
  habría que confirmarlo con las primeras llamadas reales). Estimado
  conservador: 4-12 horas de GPU. **Costo estimado: $20-$60.**

**Total estimado para dejar Palanca A calificada y lista para una
corrida formal: entre $30 y $100 de cómputo GPU on-demand**, sin
contar tiempo de configuración (instalar Ollama/driver, descargar el
modelo ~40GB, primera calibración). Es una cifra chica frente al valor
de la decisión — el riesgo real no es el costo de probar, es el tiempo
de Capa 8/Cesar en configurar y validar.

**Advertencia explícita sobre hosting sostenido** (si en el futuro se
decide dejar el modelo grande siempre encendido en vez de por lotes):
A100 80GB on-demand 24/7 ronda **~$3,600/mes** — orden de magnitud
distinto al uso por lotes. No se recomienda ese modo para el patrón de
uso actual del analizador.

## Bloqueante real detectado (gratis, verificar antes de cualquier gasto)

La cuota de GPU de este proyecto GCP **no se pudo verificar desde esta
sesión** — la cuenta de servicio de la VM (`733435082116-compute@
developer.gserviceaccount.com`) no tiene el alcance de autenticación
necesario para consultar cuotas vía API (`Request had insufficient
authentication scopes`). Por defecto, los proyectos GCP nuevos tienen
**cuota de GPU en 0** — casi seguro habrá que pedir un aumento de cuota
en la consola de GCP (gratis, pero puede tardar horas a días en
aprobarse) **antes** de poder crear cualquier instancia con GPU.

## Primer paso concreto recomendado (gratis, sin compromiso de gasto)

1. Verificar/solicitar cuota de GPU (A100) para `hotel-bot-project-492723`
   en `us-east1` (o la región más barata/disponible) desde la consola de
   GCP — requiere acceso de consola, no disponible desde esta sesión.
2. Con la cuota aprobada, crear una VM efímera de prueba (no
   `ivr-ia` — una VM nueva y separada, para no arriesgar el servicio
   base en producción), instalar Ollama, descargar el modelo, correr el
   fixture 7P+2N como calificación — mismo criterio de éxito ya
   establecido (`recall≥6/7` positivos + `2/2` negativos rechazados).
3. Solo si el fixture califica: decidir si el resultado justifica el
   costo de una corrida formal sobre el corpus completo.

**Nada de esto se ejecuta sin tu aprobación explícita en cada paso** —
mismo protocolo del resto del proyecto. Este documento es investigación
y estimación, no un plan de implementación autorizado.

## Fuentes consultadas (precios de lista, verificar en consola oficial antes de decidir)

- [Cloud GPU Pricing Comparison: AWS Vs Azure Vs GCP For AI Workloads (2026)](https://www.cloudzero.com/blog/cloud-gpu-pricing-comparison/)
- [Google Cloud Platform GPU Pricing 2026 – H100 & A100 Costs](https://gpucost.org/provider/gcp)
- [Google Cloud GPU Instances: Every Machine Type, Spec, and Price (2026)](https://www.thundercompute.com/blog/google-cloud-gpu-instances)
- [Cloud GPU Pricing 2026: A100 $1.99/hr, H100 $3.29/hr+](https://www.synpixcloud.com/blog/cloud-gpu-pricing-comparison-2026)
- [Google Cloud GPU Pricing 2026 — H100, A100 & RTX Hourly Rates](https://computecomparison.com/provider/google-cloud)
- [Running 70B Models Locally — Exact VRAM by Quantization](https://insiderllm.com/guides/running-70b-models-locally-vram-guide/)
- [VRAM for 70B Models: Why 16GB GPU Is the Minimum in 2026](https://www.sitepoint.com/vram-requirements-70b-models-16gb-gpu-minimum-2026/)
- [Self-Hosting LLaMA 3.1 70B (or any ~70B LLM) Affordably](https://abhinand05.medium.com/self-hosting-llama-3-1-70b-or-any-70b-llm-affordably-2bd323d72f8d)
