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

Para probar el estado del partido sin el motor de simulación:

```bash
python -m pytest tests/test_match_state.py -q
```

Estas pruebas usan un mock del motor con estados controlados y una base SQLite
temporal. Cubren publicación y consulta del estado, acceso, concurrencia,
movimiento mediante un comportamiento y la secuencia inicio, gol, pausa,
reanudación y fin del partido.


## Ver un partido de prueba en el navegador

Sin creación/inicio de partidos ni motor, el script genera dos usuarios, dos
clubes, seis jugadores por club (tres en cancha), una sala y un partido iniciado.
Publica estados mediante el mismo servicio que usa la API. Los movimientos y
goles son simulados; no ejecuta los comportamientos de los jugadores.

Usar tres terminales:

1. Backend, desde `futbot-backend`, con el entorno virtual activado:

   ```bash
   python -m uvicorn app.main:app --reload
   ```

2. Frontend, desde `futbot-frontend`:

   ```bash
   npm run dev
   ```

3. Demo, desde `futbot-backend`, con el entorno virtual activado:

   ```bash
   python -m scripts.demo_match
   ```

El script usa `DATABASE_URL` del mismo `.env` que el backend (por defecto
`futbot.db`). Ejecutar ambos desde esta carpeta para compartir la base SQLite.
No borra datos: cada ejecución agrega cuentas y un partido nuevos.

La terminal imprime los dos emails, la contraseña `FutbotDemo123!`, el ID y la
URL del partido. Iniciar sesión en `http://localhost:5173/login` con uno de esos
emails y abrir la URL `/matches/<ID>` indicada (o ingresar el ID en Home).
Después, presionar **Enter en la terminal de la demo** para comenzar.

Durante dos minutos publica una actualización por segundo: movimientos,
posesión, reloj, gol local a los 40 segundos, gol visitante a los 80 y resultado
final 1–1. La cancha usa la escala provisional 100 × 60, con origen en el centro.
Para probar ambos usuarios, usar otro perfil o una ventana de incógnito.

Opciones:

```bash
python -m scripts.demo_match --static           # Solo estado inicial, sin animación
python -m scripts.demo_match --duration 60      # Demo de un minuto
python -m scripts.demo_match --no-wait          # Animación inmediata, sin Enter
python -m scripts.demo_match --frontend-url http://localhost:5174
```

`Ctrl+C` detiene las publicaciones y conserva el último estado. Para volver a
empezar, ejecutar el comando nuevamente y usar las nuevas credenciales y URL.
Si la sesión vence durante una demo larga, volver a iniciar sesión y abrir la URL.
El frontend debe apuntar al backend mediante `VITE_API_URL` y su origen debe
estar incluido en `CORS_ORIGINS`.

## Estado del partido por WebSocket

El frontend mantiene una conexión a `/api/matches/{match_id}/ws`; no consulta
periódicamente el endpoint HTTP de estado. Configurar `VITE_WS_URL` en el
frontend (por ejemplo `ws://localhost:8000`, o `wss://` si se usa HTTPS).
Si no se configura, deriva esa URL de `VITE_API_URL`.

El primer mensaje del cliente es `{"type":"auth","token":"<access_token>"}`.
El servidor valida la sesión y la pertenencia a uno de los clubes antes de
enviar datos. El token no se envía en la URL. El origen del navegador debe
estar permitido en `CORS_ORIGINS`.

Mensajes del servidor:

- `{"type":"state","state":{...}}`: snapshot completo, con `match_id` y
  `revision`. Se envía el último al conectar y los nuevos al publicarse.
- `{"type":"error","status":409,"message":"..."}`: todavía no hay estado;
  la conexión permanece abierta hasta la primera publicación.
- Otros errores: `401` (sesión), `403` (acceso), `404` (partido), `422` (ID).
  Estos cierran la conexión y no provocan reintentos del frontend.
- `{"type":"ping"}` cada 15 segundos; el cliente responde
  `{"type":"pong"}`. Es mantenimiento de conexión, no consulta de estado.

La implementación actual usa notificaciones nativas del sistema de archivos
para SQLite, incluyendo el journal y WAL. Detecta commits del script demo en
otro proceso sin sondear periódicamente la base. Requiere SQLite en archivo
local y un sistema de archivos con soporte de notificaciones. PostgreSQL,
SQLite en memoria o despliegues distribuidos necesitan otro adaptador de
notificaciones (por ejemplo LISTEN/NOTIFY o pub/sub).

Ante una desconexión, la pantalla conserva el último snapshot con una advertencia
y reconecta con espera progresiva de 1 a 10 segundos. Al reconectar recibe el
estado vigente y descarta revisiones anteriores. Al finalizar, cierra el socket.
La sesión se comprueba al conectar y ante cambios de la base; la expiración del
token también cierra la conexión aunque no se publique ningún estado.

El script demo se ejecuta con los mismos comandos anteriores. Para probar el
stream y sus permisos: `python -m pytest tests/test_match_websocket.py -q`.

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
