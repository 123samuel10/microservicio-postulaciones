from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import get_settings
from app.controllers.postulacion_controller import router as postulacion_router

settings = get_settings()

DESCRIPTION = """
## Microservicio de Postulaciones

Gestiona las postulaciones de estudiantes a vacantes de práctica en **Emplea Humboldt**.

### Flujo de una postulación
1. El estudiante crea una postulación en `POST /api/v1/postulaciones/` indicando la vacante.
2. La empresa revisa y cambia el estado vía `PATCH /api/v1/postulaciones/{id}/estado`.
3. El estudiante puede retirar su postulación en cualquier momento.

### Estados de una postulación
`ENVIADA` → `EN_REVISION` → `PRESELECCIONADA` → `ACEPTADA` / `RECHAZADA`

O bien: `RETIRADA` (por el estudiante)

### Documentos soportados
- `hoja_de_vida` — CV del estudiante
- `carta_presentacion` — carta de presentación
- `certificado_notas` — certificado de calificaciones
"""

TAGS_METADATA = [
    {
        "name": "Postulaciones",
        "description": "Crear, consultar y gestionar el ciclo de vida de postulaciones. Empresas cambian estados; estudiantes se postulan y retiran.",
    },
    {
        "name": "Health",
        "description": "Verificación del estado del servicio.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # El esquema de la BD lo gestiona Alembic (entrypoint.sh -> alembic upgrade head), no create_all.
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    root_path="/postulaciones",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(postulacion_router, prefix="/api/v1")


@app.get("/health", tags=["Health"], summary="Estado del servicio")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        tags=TAGS_METADATA,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token JWT obtenido en el microservicio de autenticación.",
        }
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
