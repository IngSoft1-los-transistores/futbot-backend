# FutBot — Backend

API del juego FutBot: un juego multijugador de fútbol en el que los futbolistas no se controlan con teclado ni mouse, sino con comportamientos programados en Python por los propios usuarios.

Este repositorio implementa el manejo de datos y la lógica de negocio. La interfaz de usuario vive en [futbot-frontend](https://github.com/IngSoft1-los-transistores/futbot-frontend).

**Materia:** Ingeniería de Software I· **Equipo:** Los Transistores


## Stack

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11+ |
| Framework | FastAPI |
| Servidor | Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Validación | Pydantic v2 |
| Base de datos | SQLite (desarrollo) |
| Tests | pytest + httpx |

## Requisitos previos

- **Python 3.11 o superior** — verificar con `python --version` (en Linux y macOS puede ser `python3 --version`)
- **Git**

## Instalación

**1. Clonar el repositorio**

```bash
git clone https://github.com/IngSoft1-los-transistores/futbot-backend.git
cd futbot-backend
```

**2. Crear y activar el entorno virtual**

Linux, macOS o Git Bash en Windows:

```bash
python -m venv .venv
source .venv/bin/activate
```

PowerShell en Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> Si PowerShell bloquea el script, ejecutar una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Cuando el entorno está activo, el prompt muestra `(.venv)` al principio. **Todos los comandos siguientes se ejecutan con el entorno activo.**

**3. Instalar las dependencias**

```bash
pip install -r requirements.txt
```

**4. Configurar las variables de entorno**

```bash
cp .env.example .env
```

Abrir el `.env` y cambiar `JWT_SECRET_KEY` por una cadena aleatoria. Para generar una:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

El archivo `.env` **no se sube al repositorio**: contiene secretos y es propio de cada máquina.

## Comandos rápidos con make

El `Makefile` de la raíz agrupa los comandos de uso diario. Usa directamente el Python del `.venv`, así que **no hace falta activar el entorno virtual** para correrlos.

**Instalar make**

| Sistema | Cómo |
|---|---|
| Linux / WSL | `sudo apt install make` (en Ubuntu suele venir instalado) |
| macOS | `xcode-select --install` |
| Windows | `winget install ezwinports.make` y reiniciar la terminal |

Funciona igual desde PowerShell, Git Bash, WSL, Linux y macOS.

**Comandos**

| Comando | Qué hace |
|---|---|
| `make help` | Lista los comandos disponibles |
| `make install` | Crea el `.venv` si no existe e instala las dependencias |
| `make reinstall` | Borra el `.venv` y lo crea de cero |
| `make dev` | Levanta la API en http://localhost:8000 con recarga automática |
| `make dev PORT=8001` | Lo mismo, en otro puerto |
| `make test` | Corre los tests y muestra la cobertura en la terminal |
| `make coverage` | Igual que `make test`, y además genera el reporte en `htmlcov/index.html` |
| `make lint` | Revisa el código con [Ruff](https://docs.astral.sh/ruff/) (reglas en `ruff.toml`) |
| `make clean` | Borra cachés y reportes. No toca `.env`, `.venv` ni `futbot.db` |

`make test` devuelve código de salida distinto de 0 si algún test falla, así que sirve para CI.

**Windows y WSL:** el `.venv` es propio de cada sistema, así que uno creado desde Windows no funciona en WSL ni al revés. Si se usa WSL, clonar el repo dentro de WSL (por ejemplo en `~/`), no trabajar sobre `/mnt/c/...`: además de evitar el problema, es mucho más rápido. `make reinstall` queda para cuando el entorno se rompe o se cambia de sistema sobre la misma carpeta. Si `make dev` estaba corriendo, reiniciarlo después: sigue usando el `.venv` viejo hasta que se corta.

## Correr la aplicación

```bash
uvicorn app.main:app --reload
```

| URL | Qué es |
|---|---|
| http://localhost:8000 | La API |
| http://localhost:8000/docs | Documentación interactiva (Swagger), para probar los endpoints a mano |
| http://localhost:8000/redoc | Documentación alternativa |

La opción `--reload` reinicia el servidor solo cada vez que se guarda un archivo. Se usa únicamente en desarrollo.

Para detenerlo: `Ctrl+C`.

## Correr los tests

```bash
pytest
```

Con más detalle por test:

```bash
pytest -v
```

Con reporte de cobertura, indicando qué líneas no cubre ningún test:

```bash
pytest --cov=app --cov-report=term-missing
```

Un solo archivo o un solo test:

```bash
pytest tests/test_auth.py
pytest tests/test_auth.py::test_register_con_email_duplicado
```


## Base de datos

En desarrollo se usa SQLite: la base es un único archivo (`futbot.db`) que se crea solo al levantar la aplicación por primera vez. No requiere instalación ni servidor.

El archivo está en el `.gitignore`: cada integrante tiene su propia copia local.

Para empezar de cero, alcanza con borrarlo:

```bash
rm futbot.db
```

Al volver a levantar la aplicación se recrean las tablas y se cargan los comportamientos por defecto.



## Problemas frecuentes

**`ModuleNotFoundError` al correr uvicorn o pytest**
El entorno virtual no está activo. El prompt tiene que mostrar `(.venv)`.

**El frontend recibe errores de CORS**
Verificar que `CORS_ORIGINS` en el `.env` incluya la URL exacta del frontend, con protocolo y puerto (`http://localhost:5173`).

**El puerto 8000 está ocupado**

```bash
uvicorn app.main:app --reload --port 8001
```

Si se cambia el puerto, hay que actualizar `VITE_API_URL` y `VITE_WS_URL` en el frontend.
