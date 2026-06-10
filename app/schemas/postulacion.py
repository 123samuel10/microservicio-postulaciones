from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.postulacion import EstadoPostulacion, TipoDocumentoPostulacion


# --- Documentos ---

class DocumentoPostulacionResponse(BaseModel):
    id: uuid.UUID
    tipo: TipoDocumentoPostulacion
    url: str
    nombre_archivo: Optional[str] = None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# --- Historial ---

class HistorialEstadoResponse(BaseModel):
    id: uuid.UUID
    estado_anterior: Optional[EstadoPostulacion] = None
    estado_nuevo: EstadoPostulacion
    cambiado_por: str
    motivo: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Postulación ---

class PostulacionCreate(BaseModel):
    vacante_id: uuid.UUID
    nota_estudiante: Optional[str] = Field(None, max_length=1000)


class CambioEstadoRequest(BaseModel):
    nuevo_estado: EstadoPostulacion
    motivo: Optional[str] = Field(None, max_length=500)


class PostulacionResponse(BaseModel):
    id: uuid.UUID
    vacante_id: uuid.UUID
    estudiante_id: uuid.UUID
    empresa_id: uuid.UUID
    estado: EstadoPostulacion
    nota_estudiante: Optional[str] = None
    nota_empresa: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    documentos: List[DocumentoPostulacionResponse] = []
    historial: List[HistorialEstadoResponse] = []

    model_config = {"from_attributes": True}


class PostulacionResumenResponse(BaseModel):
    id: uuid.UUID
    vacante_id: uuid.UUID
    estudiante_id: uuid.UUID
    empresa_id: uuid.UUID
    estado: EstadoPostulacion
    # Nota de la empresa, visible para el estudiante en su listado.
    nota_empresa: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Nota empresa ---

class NotaEmpresaRequest(BaseModel):
    nota: str = Field(max_length=1000)


# --- Documento upload ---

class DocumentoUploadResponse(BaseModel):
    postulacion_id: uuid.UUID
    tipo: TipoDocumentoPostulacion
    url: str
    mensaje: str


# --- Métricas ---

class MetricasPostulaciones(BaseModel):
    total: int
    por_estado: dict
    tasa_conversion_aceptado: float
    tasa_rechazo: float
    postulaciones_por_vacante: dict
    postulaciones_por_estudiante: dict
