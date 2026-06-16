from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.deps import UsuarioToken, get_current_user, require_empresa, require_estudiante
from app.database import get_db
from app.models.postulacion import TipoDocumentoPostulacion
from app.schemas.postulacion import (
    CambioEstadoRequest,
    DocumentoUploadResponse,
    MetricasPostulaciones,
    NotaEmpresaRequest,
    PostulacionCreate,
    PostulacionResponse,
    PostulacionResumenResponse,
)
from app.services.postulacion_service import PostulacionService

router = APIRouter(prefix="/postulaciones", tags=["Postulaciones"])


@router.post("", response_model=PostulacionResponse, status_code=status.HTTP_201_CREATED)
async def crear_postulacion(
    datos: PostulacionCreate,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_estudiante),
):
    service = PostulacionService(db)
    return await service.crear_postulacion(usuario.id, datos, usuario.raw_token)


@router.get("/mis-postulaciones", response_model=List[PostulacionResumenResponse])
async def mis_postulaciones(
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_estudiante),
):
    service = PostulacionService(db)
    return await service.mis_postulaciones(usuario.id)


@router.get("/empresa/todas", response_model=List[PostulacionResumenResponse])
async def postulaciones_de_empresa(
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PostulacionService(db)
    return await service.postulaciones_de_empresa(usuario.id)


@router.get("/vacante/{vacante_id}", response_model=List[PostulacionResumenResponse])
async def postulaciones_por_vacante(
    vacante_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PostulacionService(db)
    return await service.postulaciones_por_vacante(uuid.UUID(vacante_id), usuario.id)


@router.get("/metricas", response_model=MetricasPostulaciones)
async def metricas(
    db: AsyncSession = Depends(get_db),
    _: UsuarioToken = Depends(get_current_user),
):
    service = PostulacionService(db)
    return await service.get_metricas()


@router.get("/{postulacion_id}", response_model=PostulacionResponse)
async def get_postulacion(
    postulacion_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(get_current_user),
):
    service = PostulacionService(db)
    return await service.get_postulacion(uuid.UUID(postulacion_id), usuario.id)


@router.post("/{postulacion_id}/retirar", response_model=PostulacionResponse)
async def retirar_postulacion(
    postulacion_id: str,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_estudiante),
):
    service = PostulacionService(db)
    return await service.retirar_postulacion(uuid.UUID(postulacion_id), usuario.id)


@router.patch("/{postulacion_id}/estado", response_model=PostulacionResponse)
async def cambiar_estado(
    postulacion_id: str,
    datos: CambioEstadoRequest,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PostulacionService(db)
    return await service.cambiar_estado_empresa(
        uuid.UUID(postulacion_id), usuario.id, datos.nuevo_estado, datos.motivo
    )


@router.patch("/{postulacion_id}/nota", response_model=PostulacionResponse)
async def agregar_nota_empresa(
    postulacion_id: str,
    datos: NotaEmpresaRequest,
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_empresa),
):
    service = PostulacionService(db)
    return await service.agregar_nota_empresa(uuid.UUID(postulacion_id), usuario.id, datos.nota)


@router.post("/{postulacion_id}/documentos/{tipo}", response_model=DocumentoUploadResponse)
async def subir_documento(
    postulacion_id: str,
    tipo: TipoDocumentoPostulacion,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    usuario: UsuarioToken = Depends(require_estudiante),
):
    service = PostulacionService(db)
    url = await service.subir_documento(uuid.UUID(postulacion_id), usuario.id, tipo, file)
    return DocumentoUploadResponse(
        postulacion_id=uuid.UUID(postulacion_id),
        tipo=tipo,
        url=url,
        mensaje="Documento subido correctamente",
    )
