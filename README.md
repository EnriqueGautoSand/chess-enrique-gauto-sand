# Motor de Ajedrez Humano - Enrique Gauto Sand

Plataforma de ajedrez inteligente con interfaz web moderna desarrollada en Flask, que integra motores heurísticos pedagógicos (Shannon Tipo B), redes neuronales Transformers y NNUE, y un sistema de coaching con perfiles de ELO (400 a 2600+).

---

## 🌟 Características Principales

- **Tablero Web Moderno e Interactivo:** Renderizado fluido con soporte completo para Drag & Drop y selección por clics (Click-to-Move).
- **Motores de IA Explicables:**
  - **Minimax2 (Shannon Tipo B):** Motor táctico selectivo que evalúa líneas forzadas de quietud y material.
  - **HumanChessEngine:** Motor pedagógico con desglose de conceptos (jaques, capturas SEE, tenedores, clavadas, ataques a la descubierta, profilaxis, defensa adaptativa y finales).
  - **Transformers & NNUE:** Modelos de evaluación posicional y profunda (Token Transformers, Rich Transformers y Dual-Head 1M dynamic).
- **Selector de Nivel ELO con Heurísticas Reales:** Simulación de juego desde 400 hasta 2600+ ELO basada en 55 técnicas tácticas granulares calibradas estadísticamente.
- **Navegación y Ramificación de Partidas:** Historial interactivo con botones de navegación (<, >), carga/exportación de FEN y PGN, y capacidad de reanudar o ramificar desde cualquier jugada anterior.
- **Personalización Visual Completa:** Múltiples temas de tablero y piezas vectoriales (Staunton, Wood, Cyberpunk, Pixel, Art Deco, Wireframe, Madera 2D, etc.).

---

## 🚀 Instalación y Ejecución Local

### Requisitos Previos
- Python 3.10 o superior (recomendado Python 3.12).
- Git.

### 1. Clonar el repositorio
`ash
git clone https://github.com/TU_USUARIO/chess-enrique-gauto-sand.git
cd chess-enrique-gauto-sand
`

### 2. Crear y activar un entorno virtual
**En Windows (PowerShell):**
`powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
`

**En Linux / macOS:**
`ash
python3 -m venv .venv
source .venv/bin/activate
`

### 3. Instalar dependencias
`ash
pip install -r requirements.txt
`

### 4. Iniciar el servidor
`ash
python app.py
`
Abre tu navegador en http://127.0.0.1:5000.

---

## 🌐 Cómo Desplegar 24/7 Gratis en la Nube

> **Nota sobre GitHub Pages:** GitHub Pages únicamente aloja páginas estáticas (HTML/CSS/JS) y no puede ejecutar el backend de Flask ni los motores en Python. Para tener el motor funcionando 24/7 en línea, se recomiendan las siguientes plataformas gratuitas:

### Opción 1: Hugging Face Spaces (Recomendada 24/7)
1. Crea una cuenta gratuita en [Hugging Face](https://huggingface.co/).
2. Ve a **Spaces** > **Create new Space**.
3. Selecciona **Docker** o **Gradio/Blank** con SDK Python.
4. Conecta tu repositorio de GitHub o sube los archivos.
5. Hugging Face compilará y mantendrá tu aplicación corriendo **24/7 con 16 GB de RAM y 2 vCPUs de forma gratuita**.

### Opción 2: Render.com (Web Service)
1. Crea una cuenta en [Render.com](https://render.com/).
2. Haz clic en **New +** > **Web Service**.
3. Conecta este repositorio de GitHub.
4. Configuración:
   - **Environment:** Python 3
   - **Build Command:** pip install -r requirements.txt
   - **Start Command:** gunicorn app:app --bind 0.0.0.0:
5. Haz clic en **Deploy Web Service**.

### Opción 3: Google Cloud Run (Nivel Gratuito de Google Cloud)
- Permite desplegar el contenedor de Flask con un crédito mensual gratuito de hasta 2 millones de peticiones.

---

## 🧪 Pruebas Automatizadas

Para validar que todos los endpoints y la lógica del motor funcionan correctamente:

`ash
python -m unittest test_app.py
python -m unittest test_pve.py
`

---

## 📄 Licencia

Este proyecto está bajo la licencia **GNU AGPLv3**.
Consulte el archivo [LICENSE](LICENSE) para más detalles.
Para licencias comerciales privadas o integraciones empresariales, contactar a: **egsand98@gmail.com**.
