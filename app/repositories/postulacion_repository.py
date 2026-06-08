from __future__ import annotations

import uuid
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.postulacion import (
    Postulacion,
    DocumentoPostulacion,
    HistorialEstado,
    EstadoPostulacion,
    TipoDocumentoPostulacion,
)


class PostulacionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, postulacion_id: uuid.UUID) -> Optional[Postulacion]:
        result = await self.db.execute(
            select(Postulacion)
            .options(
                selectinload(Postulacion.documentos),
                selectinload(Postulacion.historial),
            )
            .where(Postulacion.id == postulacion_id)
        )
        return result.scalar_one_or_none()

    async def get_by_vacante_y_estudiante(
        self, vacante_id: uuid.UUID, estudiante_id: uuid.UUID
    ) -> Optional[Postulacion]:
        result = await self.db.execute(
            select(Postulacion).where(
                Postulacion.vacante_id == vacante_id,
                Postulacion.estudiante_id == estudiante_id,
            )
        )
        return result.scalar_one_or_none()

    async def listar_por_estudiante(self, estudiante_id: uuid.UUID) -> List[Postulacion]:
        result = await self.db.execute(
            select(Postulacion)
            .options(selectinload(Postulacion.documentos), selectinload(Postulacion.historial))
            .where(Postulacion.estudiante_id == estudiante_id)
            .order_by(Postulacion.created_at.desc())
        )
        return list(result.scalars().all())

    async def listar_por_vacante(self, vacante_id: uuid.UUID) -> List[Postulacion]:
        result = await self.db.execute(
            select(Postulacion)
            .options(selectinload(Postulacion.documentos), selectinload(Postulacion.historial))
            .where(Postulacion.vacante_id == vacante_id)
            .order_by(Postulacion.created_at.desc())
        )
        return list(result.scalars().all())

    async def listar_por_empresa(self, empresa_id: uuid.UUID) -> List[Postulacion]:
        result = await self.db.execute(
            select(Postulacion)
            .options(selectinload(Postulacion.documentos), selectinload(Postulacion.historial))
            .where(Postulacion.empresa_id == empresa_id)
            .order_by(Postulacion.created_at.desc())
        )
        return list(result.scalars().all())

    async def crear(
        self,
        vacante_id: uuid.UUID,
        estudiante_id: uuid.UUID,
        empresa_id: uuid.UUID,
        nota_estudiante: Optional[str] = None,
    ) -> Postulacion:
        postulacion = Postulacion(
            vacante_id=vacante_id,
            estudiante_id=estudiante_id,
            empresa_id=empresa_id,
            nota_estudiante=nota_estudiante,
        )
        self.db.add(postulacion)
        await self.db.flush()
        await self.db.refresh(postulacion)
        return postulacion

    async def actualizar_estado(
        self,
        postulacion: Postulacion,
        nuevo_estado: EstadoPostulacion,
        cambiado_por: str,
        motivo: Optional[str] = None,
    ) -> Postulacion:
        estado_anterior = postulacion.estado
        postulacion.estado = nuevo_estado
        await self.db.flush()

        historial = HistorialEstado(
            postulacion_id=postulacion.id,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            cambiado_por=cambiado_por,
            motivo=motivo,
        )
        self.db.add(historial)
        await self.db.flush()
        await self.db.refresh(postulacion)
        return postulacion

    async def actualizar_nota_empresa(self, postulacion: Postulacion, nota: str) -> Postulacion:
        postulacion.nota_empresa = nota
        await self.db.flush()
        await self.db.refresh(postulacion)
        return postulacion

    async def contar_por_estado(self) -> dict:
        result = await self.db.execute(
            select(Postulacion.estado, func.count(Postulacion.id)).group_by(Postulacion.estado)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def contar_total(self) -> int:
        result = await self.db.execute(select(func.count(Postulacion.id)))
        return result.scalar_one()

    async def contar_por_vacante(self) -> dict:
        result = await self.db.execute(
            select(Postulacion.vacante_id, func.count(Postulacion.id))
            .group_by(Postulacion.vacante_id)
            .order_by(func.count(Postulacion.id).desc())
            .limit(20)
        )
        return {str(row[0]): row[1] for row in result.all()}

    async def contar_por_estudiante(self) -> dict:
        result = await self.db.execute(
            select(Postulacion.estudiante_id, func.count(Postulacion.id))
            .group_by(Postulacion.estudiante_id)
            .order_by(func.count(Postulacion.id).desc())
            .limit(20)
        )
        return {str(row[0]): row[1] for row in result.all()}


class DocumentoPostulacionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def crear(
        self,
        postulacion_id: uuid.UUID,
        tipo: TipoDocumentoPostulacion,
        url: str,
        nombre_archivo: Optional[str] = None,
    ) -> DocumentoPostulacion:
        doc = DocumentoPostulacion(
            postulacion_id=postulacion_id,
            tipo=tipo,
            url=url,
            nombre_archivo=nombre_archivo,
        )
        self.db.add(doc)
        await self.db.flush()
        await self.db.refresh(doc)
        return doc
