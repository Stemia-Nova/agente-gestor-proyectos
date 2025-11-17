# 🤖 Agente Gestor de Proyectos - Manual de Usuario

**Sistema de asistente inteligente para gestión ágil basado en ClickUp + RAG (Retrieval-Augmented Generation)**

---

## 📋 Tabla de Contenidos

- [¿Qué es este proyecto?](#qué-es-este-proyecto)
- [Características principales](#características-principales)
- [Requisitos previos](#requisitos-previos)
- [Instalación rápida](#instalación-rápida)
- [Configuración](#configuración)
- [Cómo usar el chatbot](#cómo-usar-el-chatbot)
- [Funcionalidades disponibles](#funcionalidades-disponibles)
- [Ejemplos de consultas](#ejemplos-de-consultas)
- [Tests y validación](#tests-y-validación)
- [Generación de informes PDF](#generación-de-informes-pdf)
- [Arquitectura técnica](#arquitectura-técnica)
- [Troubleshooting](#troubleshooting)

---

## 🎯 ¿Qué es este proyecto?

Un **asistente conversacional inteligente** que ayuda a Project Managers y equipos Scrum a:

- ✅ Consultar tareas de ClickUp mediante lenguaje natural
- 📊 Generar informes profesionales de sprints (PDF + texto)
- 🔍 Detectar bloqueos, dudas y tareas críticas
- 📈 Obtener métricas en tiempo real (completitud, progreso, etc.)
- 💬 Responder preguntas contextuales sobre el proyecto

**Ventaja clave**: No necesitas saber SQL ni filtros complejos. Habla con el chatbot como hablarías con un PM.

---

## ⚡ Características principales

### 🔢 Conteo inteligente de tareas

- **Filtros combinados**: Sprint + Estado + Persona
- **Ejemplo**: "¿cuántas tareas completadas tiene Jorge en el sprint 3?"
- **Precisión**: 100% validado con 20+ tests automatizados

### 🤖 Clasificación de intenciones con LLM

- Sistema dinámico (no hardcodeado) usando GPT-4o-mini
- Detecta automáticamente: conteos, búsquedas, informes, detalles de tareas
- Confianza medida (0-100%)

### 🔍 Búsqueda híbrida (RAG)

- **Embeddings semánticos**: sentence-transformers (all-MiniLM-L12-v2)
- **Reranking**: cross-encoder para mejorar relevancia
- **ChromaDB**: Base de datos vectorial persistente

### 📄 Generación de informes profesionales

- **Formato PDF**: Informe ejecutivo con métricas, bloqueos y recomendaciones
- **Formato texto**: Vista completa para pantalla
- **Automático**: Por defecto genera PDF + mensaje amigable

### 💬 Contexto conversacional

- Recuerda las últimas 5 interacciones
- Detecta referencias: "esa tarea", "dame más info", "¿tiene comentarios?"
- Enriquecimiento automático de consultas

### 🎨 Indicadores visuales PM-friendly

- ⚠️ **BLOQUEADA**: Tareas bloqueadas
- 🤔 **CON DUDAS**: Requieren clarificación
- ⏰ **VENCIDA**: Pasadas de fecha
- 📋 **X/Y completadas**: Progreso de subtareas

---

## 🛠️ Requisitos previos

- **Python 3.12+** (recomendado: 3.12.3)
- **Linux/WSL** (probado en Ubuntu/WSL2)
- **ClickUp API Token** ([obtener aquí](https://app.clickup.com/settings/apps))
- **OpenAI API Key** ([obtener aquí](https://platform.openai.com/api-keys))
- **8GB RAM mínimo** (para modelos de embeddings)

---

## 🚀 Instalación rápida

```bash
# 1. Clonar el repositorio
git clone https://github.com/Stemia-Nova/agente-gestor-proyectos.git
cd agente-gestor-proyectos

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales (ver sección Configuración)

# 5. Sincronizar datos de ClickUp
python data/rag/sync/update_chroma_from_clickup.py

# 6. Lanzar el chatbot
chainlit run main.py --port 8000
```

Abre tu navegador en: **http://localhost:8000**

---

## ⚙️ Configuración

### Archivo `.env`

```bash
# ClickUp
CLICKUP_API_TOKEN=pk_254517445_XXXXXXXXXX
CLICKUP_FOLDER_ID=901511269055
CLICKUP_INCLUDE_CLOSED=true

# OpenAI
OPENAI_API_KEY=sk-proj-XXXXXXXXXXXXXXXX

# ChromaDB (opcional, por defecto: data/rag/chroma_db)
CHROMA_DB_PATH=data/rag/chroma_db
CHROMA_COLLECTION=clickup_tasks
```

### Obtener credenciales:

1. **ClickUp API Token**:

   - Ve a: Settings → Apps → API Token
   - Copia el token `pk_...`

2. **ClickUp Folder ID**:

   - Abre tu carpeta en ClickUp
   - Copia el número de la URL: `https://app.clickup.com/.../folder/XXXXXXXXX`

3. **OpenAI API Key**:
   - Crea cuenta en: https://platform.openai.com
   - Ve a: API Keys → Create new secret key
   - Copia la clave `sk-proj-...`

---

## 💬 Cómo usar el chatbot

### Inicio rápido

```bash
# Activar entorno virtual
source .venv/bin/activate

# Lanzar chatbot
chainlit run main.py --port 8000
```

Abre: **http://localhost:8000**

### Flujo típico:

1. **Pregunta inicial**: "¿hay tareas bloqueadas?"
2. **Profundizar**: "dame más info" (mantiene contexto)
3. **Filtrar**: "¿cuántas tareas tiene Jorge en el sprint 3?"
4. **Generar informe**: "quiero un informe del sprint 3"

---

## 🎓 Funcionalidades disponibles

### 1. **Conteo de tareas**

| Consulta                                        | Resultado esperado                      |
| ----------------------------------------------- | --------------------------------------- |
| ¿cuántas tareas hay en total?                   | 24 tareas                               |
| ¿cuántas tareas hay en el sprint 3?             | 8 tareas                                |
| ¿cuántas tareas completadas hay en el sprint 3? | 1 tarea completada: "Crear tareas..."   |
| ¿cuántas tareas tiene Jorge?                    | 7 tareas asignadas a Jorge              |
| ¿cuántas tareas tiene Jorge en el sprint 3?     | 5 tareas en Sprint 3, asignadas a Jorge |
| ¿cuántas tareas pendientes hay en el sprint 2?  | X tareas pendientes del Sprint 2        |

### 2. **Búsqueda por características**

| Consulta                          | Resultado esperado                                      |
| --------------------------------- | ------------------------------------------------------- |
| ¿hay tareas bloqueadas?           | 1 tarea bloqueada: "Conseguir ChatBot..." (3 subtareas) |
| ¿hay tareas con comentarios?      | 1 tarea activa con comentarios (excluye completadas)    |
| ¿hay tareas con subtareas?        | 3 tareas con subtareas                                  |
| ¿hay tareas con dudas?            | No hay tareas con dudas (o lista si existen)            |
| ¿hay tareas con la etiqueta data? | 4 tareas con tag "data"                                 |

### 3. **Información detallada**

| Consulta                                     | Resultado esperado                                                |
| -------------------------------------------- | ----------------------------------------------------------------- |
| dame info sobre la tarea "Conseguir ChatBot" | Estado, sprint, prioridad, asignado, subtareas, comentarios       |
| ¿qué subtareas tiene?                        | Lista de subtareas con estados (Completada, Bloqueada, Pendiente) |
| ¿tiene comentarios?                          | Número de comentarios + resumen si disponible                     |

### 4. **Generación de informes**

| Consulta                              | Resultado esperado                             |
| ------------------------------------- | ---------------------------------------------- |
| quiero un informe del sprint 3        | Genera PDF + mensaje amigable con ruta         |
| genera informe pdf del sprint 2       | PDF profesional con métricas y recomendaciones |
| muestra informe del sprint 3 en texto | Informe completo en pantalla (sin PDF)         |

### 5. **Métricas de sprint**

| Consulta                       | Resultado esperado                               |
| ------------------------------ | ------------------------------------------------ |
| dame las métricas del sprint 2 | Completitud %, tareas por estado, alta prioridad |
| compara sprint 1 y sprint 2    | Comparación lado a lado de métricas              |

### 6. **Búsqueda semántica**

| Consulta                   | Resultado esperado                                    |
| -------------------------- | ----------------------------------------------------- |
| ¿qué tareas hay sobre RAG? | Tareas relacionadas con "RAG" (embeddings semánticos) |
| tareas de embeddings       | Busca por similitud semántica                         |

---

## 📝 Ejemplos de consultas

### Ejemplo 1: Detectar bloqueos

```
Usuario: ¿hay tareas bloqueadas?
Bot: Hay 1 tarea bloqueada: "Conseguir que nuestro ChatBot conteste a nuestras preguntas" (3 subtareas).

Usuario: dame más info
Bot: La tarea "Conseguir que nuestro ChatBot..." está en estado Pendiente,
     Sprint 3, prioridad Normal, asignada a Jorge Aguadero.
     Tiene 3 subtareas:
     - Subtarea 1 [Completada]
     - Subtarea 2 [Bloqueada] ⚠️
     - Subtarea 3 [Pendiente]
     No tiene comentarios.
```

### Ejemplo 2: Conteo combinado

```
Usuario: ¿cuántas tareas completadas tiene Jorge en el sprint 3?
Bot: Hay 0 tareas en el Sprint 3, asignadas a Jorge completadas.
```

### Ejemplo 3: Generar informe

```
Usuario: quiero un informe del sprint 3
Bot: 📄 **Informe generado exitosamente**

     ✅ Sprint: Sprint 3
     📁 Archivo: `data/logs/informe_sprint_3_20251117_1300.pdf`

     💡 **Resumen rápido:**
     • Puedes abrir el PDF para ver el informe completo profesional
     • Si prefieres verlo aquí, pregunta: 'muestra informe del Sprint 3 en texto'

     El PDF incluye: métricas, tareas detalladas, bloqueos críticos y recomendaciones.
```

---

## 🧪 Tests y validación

### Test completo (20 tests)

```bash
# Ejecutar batería completa de tests
python test_funcionalidades_completas.py
```

**Resultado esperado**: 20/20 tests pasados (100%)

### Tests específicos

```bash
# Test de conteo corregido
python test_count_improved.py

# Test de contexto conversacional
python test_context_mejorado.py

# Test de UX de informes
python test_informe_ux.py
```

### Validación de datos

```bash
# Verificar integridad RAW → ChromaDB
python tools/compare_clickup_vs_chroma.py

# Inspeccionar base de datos vectorial
python tools/inspect_chroma.py
```

---

## 📄 Generación de informes PDF

### Formato del informe profesional:

```
═══════════════════════════════════════════════════════════
INFORME DE SPRINT - Sprint 3
═══════════════════════════════════════════════════════════
Fecha: 17/11/2025 13:00
Preparado para: Project Manager / Scrum Master

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RESUMEN EJECUTIVO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total de Tareas: 8
Completadas: 1 (12.5%)
En Progreso: 1
Pendientes: 4
Bloqueadas: 1 ⚠️ REQUIERE ATENCIÓN

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DETALLE DE TAREAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ TAREAS COMPLETADAS
• Crear tareas para Sprint 2 (Laura Pérez Lopez)

⏳ PENDIENTES
• Conseguir ChatBot (Jorge Aguadero) - 3 subtareas ⚠️ BLOQUEADA
• Hacer chunks (Jorge Aguadero)
• Hacer embeddings (Jorge Aguadero)
• Alimentar LLM (Jorge Aguadero)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ BLOQUEOS CRÍTICOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Conseguir ChatBot
├─ Estado: Pendiente
├─ Asignado: Jorge Aguadero
├─ 📎 Subtareas: 3 (1/3 completadas, 1 bloqueada ⚠️)
└─ Acción: Reunión para desbloquear

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 RECOMENDACIONES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ Resolver 1 bloqueo antes de continuar
📌 Sprint con avance bajo (12.5%) - revisar capacidad
```

### Ubicación de PDFs generados:

```
data/logs/informe_sprint_X_YYYYMMDD_HHMM.pdf
```

---

## 🏗️ Arquitectura técnica

### Stack tecnológico:

```
Frontend:       Chainlit (interfaz web conversacional)
Backend:        Python 3.12
LLM:            OpenAI GPT-4o-mini
Embeddings:     sentence-transformers (all-MiniLM-L12-v2)
Reranker:       cross-encoder (ms-marco-MiniLM-L-12-v2)
Vector DB:      ChromaDB 0.5.5
API:            ClickUp REST API
PDF:            ReportLab
```

### Flujo de datos:

```
ClickUp API
    ↓
[Ingest] clickup_tasks_all.json
    ↓
[Transform] clean → markdown → natural → chunks
    ↓
[Index] embeddings → ChromaDB
    ↓
[Query] Usuario → Clasificador de intenciones → HybridSearch
    ↓
[Retrieve] Semantic search + Reranker
    ↓
[Generate] GPT-4o-mini + Contexto → Respuesta
```

### Módulos principales:

```
utils/
├── hybrid_search.py          # Motor RAG híbrido
├── intent_classifier.py      # Clasificación LLM de intenciones
├── report_generator.py       # Generación de informes PDF
└── helpers.py                # Utilidades generales

chatbot/
├── handlers.py               # Manejo de consultas y contexto
└── prompts.py                # Plantillas de prompts optimizadas

data/rag/
├── ingest/                   # Datos crudos de ClickUp
├── transform/                # Pipeline de transformación
├── index/                    # Indexación vectorial
└── sync/                     # Sincronización automática
```

---

## 🔧 Troubleshooting

### Error: "OPENAI_API_KEY no está configurada"

**Solución**:

```bash
# Verificar que .env existe y tiene la clave
cat .env | grep OPENAI_API_KEY

# Si no existe, crear .env desde .env.example
cp .env.example .env
# Editar .env y añadir tu clave
```

### Error: "ChromaDB collection not found"

**Solución**:

```bash
# Regenerar la base de datos vectorial
python data/rag/sync/update_chroma_from_clickup.py
```

### El chatbot cuenta mal las tareas

**Solución**:

```bash
# Verificar integridad de datos
python tools/compare_clickup_vs_chroma.py

# Ejecutar tests de conteo
python test_count_improved.py

# Si fallan, regenerar pipeline
python run_pipeline.py
```

### Error 429: "Rate limit exceeded" (OpenAI)

**Solución**:

- Espera 1 minuto (límite: 3 RPM, 200 RPD)
- O actualiza a plan de pago para más requests

### El contexto conversacional no funciona

**Solución**:

```bash
# Verificar que handlers.py tiene las mejoras
grep "more_info_requests" chatbot/handlers.py

# Reiniciar el chatbot
pkill -f "chainlit run"
chainlit run main.py --port 8000
```

---

## 📊 Estado actual del proyecto

### ✅ Implementado y validado (100% tests):

- [x] Conteo de tareas con filtros combinados (sprint + estado + persona)
- [x] Búsqueda por comentarios (solo tareas activas)
- [x] Búsqueda por subtareas con progreso (X/Y completadas)
- [x] Búsqueda por tags (data, bloqueada, hotfix, etc.)
- [x] Detección de tareas bloqueadas con detalles
- [x] Clasificación de intenciones con LLM dinámico
- [x] Contexto conversacional (últimas 5 interacciones)
- [x] Generación de informes en PDF profesional
- [x] Generación de informes en texto
- [x] Métricas de sprint (completitud, progreso, bloqueos)
- [x] Indicadores visuales PM-friendly (⚠️🤔⏰📋)
- [x] Búsqueda híbrida (embeddings + reranker)
- [x] Sincronización automática con ClickUp
- [x] 20+ tests automatizados

### ⚠️ Limitaciones conocidas:

- **Contexto conversacional**: Funciona bien para referencias directas ("esa tarea", "más info"), pero puede confundirse con referencias ambiguas ("me los puedes facilitar?")
- **Rate limits OpenAI**: 3 RPM, 200 RPD (considera plan de pago para producción)
- **Idioma**: Optimizado para español, inglés parcial

### 🔮 Mejoras futuras sugeridas:

- [ ] Caché de embeddings para queries repetidas
- [ ] Soporte multiidioma completo (EN/ES)
- [ ] Integración con Slack/Teams
- [ ] Dashboard web con gráficas interactivas
- [ ] Alertas automáticas por email (bloqueos, vencimientos)
- [ ] Sugerencias proactivas basadas en patrones históricos

---

## 📚 Recursos adicionales

### Documentación técnica:

- **ChromaDB**: https://docs.trychroma.com
- **Sentence Transformers**: https://www.sbert.net
- **ClickUp API**: https://clickup.com/api
- **Chainlit**: https://docs.chainlit.io

### Papers relevantes:

- **RAG (Retrieval-Augmented Generation)**: Lewis et al., 2020
- **Cross-Encoder Reranking**: Nogueira & Cho, 2019

---

## 👥 Equipo

**Desarrolladores**:

- Laura Pérez Lopez
- Jorge Aguadero

**Organización**: Stemia Nova

---

## 📝 Licencia

Este proyecto es propiedad de Stemia Nova. Todos los derechos reservados.

---

## 🆘 Soporte

¿Problemas o preguntas?

1. Revisa la sección [Troubleshooting](#troubleshooting)
2. Ejecuta los tests: `python test_funcionalidades_completas.py`
3. Contacta al equipo de desarrollo

---

**Última actualización**: 17 de noviembre de 2025
**Versión**: 1.0.0 (improve_rag_creation branch)
