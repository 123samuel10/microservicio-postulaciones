from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Boolean, DateTime, Enum, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class EstadoPostulacion(str, enum.Enum):
    postulado = "postulado"
    en_revision = "en_revision"
    entrevista = "entrevista"
    aceptado = "aceptado"
    rechazado = "rechazado"
    retirado = "retirado"


# Transiciones válidas de estado
TRANSICIONES_VALIDAS: dict = {
    EstadoPostulacion.postulado:   {EstadoPostulacion.en_revision, EstadoPostulacion.rechazado, EstadoPostulacion.retirado},
    EstadoPostulacion.en_revision: {EstadoPostulacion.entrevista, EstadoPostulacion.rechazado, EstadoPostulacion.retirado},
    EstadoPostulacion.entrevista:  {EstadoPostulacion.aceptado, EstadoPostulacion.rechazado, EstadoPostulacion.retirado},
    EstadoPostulacion.aceptado:    set(),
    EstadoPostulacion.rechazado:   set(),
    EstadoPostulacion.retirado:    set(),
}


class TipoDocumentoPostulacion(str, enum.Enum):
    carta_presentacion = "carta_presentacion"
    hoja_de_vida = "hoja_de_vida"
    portafolio = "portafolio"


class Postulacion(Base):
    __tablename__ = "postulaciones"
    __table_args__ = (
        UniqueConstraint("vacante_id", "estudiante_id", name="uq_postulacion_vacante_estudiante"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vacante_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    estudiante_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    # Snapshot del empresa_id para facilitar consultas sin cruzar servicios
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    estado: Mapped[EstadoPostulacion] = mapped_column(
        Enum(EstadoPostulacion, name="estado_postulacion_enum"),
        default=EstadoPostulacion.postulado,
        nullable=False,
        index=True,
    )
    nota_estudiante: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nota_empresa: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    documentos: Mapped[List[DocumentoPostulacion]] = relationship(
        back_populates="postulacion", cascade="all, delete-orphan"
    )
    historial: Mapped[List[HistorialEstado]] = relationship(
        back_populates="postulacion", cascade="all, delete-orphan", order_by="HistorialEstado.created_at"
    )


class DocumentoPostulacion(Base):
    __tablename__ = "documentos_postulacion"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    postulacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("postulaciones.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[TipoDocumentoPostulacion] = mapped_column(
        Enum(TipoDocumentoPostulacion, name="tipo_doc_postulacion_enum"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    nombre_archivo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    postulacion: Mapped[Postulacion] = relationship(back_populates="documentos")


class HistorialEstado(Base):
    __tablename__ = "historial_estados"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    postulacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("postulaciones.id", ondelete="CASCADE"), nullable=False
    )
    estado_anterior: Mapped[Optional[EstadoPostulacion]] = mapped_column(
        Enum(EstadoPostulacion, name="estado_post_anterior_enum"), nullable=True
    )
    estado_nuevo: Mapped[EstadoPostulacion] = mapped_column(
        Enum(EstadoPostulacion, name="estado_post_nuevo_enum"), nullable=False
    )
    cambiado_por: Mapped[str] = mapped_column(String(50), nullable=False)  # "estudiante" | "empresa"
    motivo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    postulacion: Mapped[Postulacion] = relationship(back_populates="historial")
