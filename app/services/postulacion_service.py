from __future__ import annotations

import uuid
from typing import List, Optional

import boto3
import httpx
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.postulacion import (
    EstadoPostulacion,
    TipoDocumentoPostulacion,
    TRANSICIONES_VALIDAS,
)
from app.repositories.postulacion_repository import (
    DocumentoPostulacionRepository,
    PostulacionRepository,
)
from app.schemas.postulacion import (
    MetricasPostulaciones,
    PostulacionCreate,
    PostulacionResponse,
    PostulacionResumenResponse,
)

settings = get_settings()


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


async def _subir_archivo_s3(file: UploadFile, key: str) -> str:
    s3 = _s3_client()
    try:
        contenido = await file.read()
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=contenido,
            ContentType=file.content_type or "application/octet-stream",
        )
        return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error al subir el archivo: {str(e)}",
        )


async def _obtener_vacante(vacante_id: uuid.UUID, token: str) -> dict:
    """Consulta el microservicio de empleos para verificar que la vacante existe y está publicada."""
    url = f"{settings.EMPLEOS_SERVICE_URL}/api/v1/vacantes/{vacante_id}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo conectar con el servicio de empleos",
            )
    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacante no encontrada")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Error al consultar la vacante")
    return resp.json()


class PostulacionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PostulacionRepository(db)
        self.doc_repo = DocumentoPostulacionRepository(db)

    async def crear_postulacion(
        self, estudiante_id: uuid.UUID, datos: PostulacionCreate, token: str
    ) -> PostulacionResponse:
        # Verificar que la vacante existe y está publicada
        vacante = await _obtener_vacante(datos.vacante_id, token)
        if vacante.get("estado") != "publicada":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede postular a vacantes publicadas",
            )

        # Evitar postulación duplicada
        existente = await self.repo.get_by_vacante_y_estudiante(datos.vacante_id, estudiante_id)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una postulación para esta vacante",
            )

        empresa_id = uuid.UUID(vacante["empresa_id"])
        postulacion = await self.repo.crear(
            vacante_id=datos.vacante_id,
            estudiante_id=estudiante_id,
            empresa_id=empresa_id,
            nota_estudiante=datos.nota_estudiante,
        )

        # Registrar estado inicial en historial
        await self.repo.actualizar_estado(
            postulacion,
            EstadoPostulacion.postulado,
            cambiado_por="estudiante",
            motivo="Postulación creada",
        )

        postulacion = await self.repo.get_by_id(postulacion.id)
        return PostulacionResponse.model_validate(postulacion)

    async def cambiar_estado_empresa(
        self,
        postulacion_id: uuid.UUID,
        empresa_id: uuid.UUID,
        nuevo_estado: EstadoPostulacion,
        motivo: Optional[str],
    ) -> PostulacionResponse:
        postulacion = await self._get_postulacion_de_empresa(postulacion_id, empresa_id)
        self._validar_transicion(postulacion.estado, nuevo_estado, actor="empresa")
        await self.repo.actualizar_estado(postulacion, nuevo_estado, "empresa", motivo)
        postulacion = await self.repo.get_by_id(postulacion_id)
        return PostulacionResponse.model_validate(postulacion)

    async def retirar_postulacion(
        self, postulacion_id: uuid.UUID, estudiante_id: uuid.UUID
    ) -> PostulacionResponse:
        postulacion = await self._get_postulacion_de_estudiante(postulacion_id, estudiante_id)
        self._validar_transicion(postulacion.estado, EstadoPostulacion.retirado, actor="estudiante")
        await self.repo.actualizar_estado(
            postulacion, EstadoPostulacion.retirado, "estudiante", "Retirado por el estudiante"
        )
        postulacion = await self.repo.get_by_id(postulacion_id)
        return PostulacionResponse.model_validate(postulacion)

    async def agregar_nota_empresa(
        self, postulacion_id: uuid.UUID, empresa_id: uuid.UUID, nota: str
    ) -> PostulacionResponse:
        postulacion = await self._get_postulacion_de_empresa(postulacion_id, empresa_id)
        await self.repo.actualizar_nota_empresa(postulacion, nota)
        postulacion = await self.repo.get_by_id(postulacion_id)
        return PostulacionResponse.model_validate(postulacion)

    async def get_postulacion(
        self, postulacion_id: uuid.UUID, usuario_id: uuid.UUID
    ) -> PostulacionResponse:
        postulacion = await self.repo.get_by_id(postulacion_id)
        if not postulacion:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Postulación no encontrada")
        if postulacion.estudiante_id != usuario_id and postulacion.empresa_id != usuario_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta postulación")
        return PostulacionResponse.model_validate(postulacion)

    async def mis_postulaciones(self, estudiante_id: uuid.UUID) -> List[PostulacionResumenResponse]:
        postulaciones = await self.repo.listar_por_estudiante(estudiante_id)
        return [PostulacionResumenResponse.model_validate(p) for p in postulaciones]

    async def postulaciones_por_vacante(
        self, vacante_id: uuid.UUID, empresa_id: uuid.UUID
    ) -> List[PostulacionResumenResponse]:
        postulaciones = await self.repo.listar_por_vacante(vacante_id)
        if postulaciones and postulaciones[0].empresa_id != empresa_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta vacante")
        return [PostulacionResumenResponse.model_validate(p) for p in postulaciones]

    async def postulaciones_de_empresa(self, empresa_id: uuid.UUID) -> List[PostulacionResumenResponse]:
        postulaciones = await self.repo.listar_por_empresa(empresa_id)
        return [PostulacionResumenResponse.model_validate(p) for p in postulaciones]

    async def subir_documento(
        self,
        postulacion_id: uuid.UUID,
        estudiante_id: uuid.UUID,
        tipo: TipoDocumentoPostulacion,
        file: UploadFile,
    ) -> str:
        postulacion = await self._get_postulacion_de_estudiante(postulacion_id, estudiante_id)
        if postulacion.estado not in {EstadoPostulacion.postulado, EstadoPostulacion.en_revision}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden subir documentos en estado postulado o en revisión",
            )
        key = f"postulaciones/{postulacion_id}/{tipo.value}/{file.filename}"
        url = await _subir_archivo_s3(file, key)
        await self.doc_repo.crear(postulacion_id, tipo, url, file.filename)
        return url

    async def get_metricas(self) -> MetricasPostulaciones:
        total = await self.repo.contar_total()
        por_estado = await self.repo.contar_por_estado()
        por_vacante = await self.repo.contar_por_vacante()
        por_estudiante = await self.repo.contar_por_estudiante()

        aceptados = por_estado.get("aceptado", 0)
        rechazados = por_estado.get("rechazado", 0)
        tasa_conversion = round(aceptados / total, 4) if total else 0.0
        tasa_rechazo = round(rechazados / total, 4) if total else 0.0

        return MetricasPostulaciones(
            total=total,
            por_estado=por_estado,
            tasa_conversion_aceptado=tasa_conversion,
            tasa_rechazo=tasa_rechazo,
            postulaciones_por_vacante=por_vacante,
            postulaciones_por_estudiante=por_estudiante,
        )

    # --- helpers privados ---

    def _validar_transicion(
        self, estado_actual: EstadoPostulacion, nuevo_estado: EstadoPostulacion, actor: str
    ) -> None:
        if nuevo_estado not in TRANSICIONES_VALIDAS.get(estado_actual, set()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Transición inválida: {estado_actual} → {nuevo_estado}",
            )
        # El estudiante solo puede retirar; la empresa no puede retirar
        if actor == "estudiante" and nuevo_estado != EstadoPostulacion.retirado:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El estudiante solo puede retirar su postulación",
            )
        if actor == "empresa" and nuevo_estado == EstadoPostulacion.retirado:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La empresa no puede retirar una postulación",
            )

    async def _get_postulacion_de_empresa(
        self, postulacion_id: uuid.UUID, empresa_id: uuid.UUID
    ):
        postulacion = await self.repo.get_by_id(postulacion_id)
        if not postulacion:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Postulación no encontrada")
        if postulacion.empresa_id != empresa_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta postulación")
        return postulacion

    async def _get_postulacion_de_estudiante(
        self, postulacion_id: uuid.UUID, estudiante_id: uuid.UUID
    ):
        postulacion = await self.repo.get_by_id(postulacion_id)
        if not postulacion:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Postulación no encontrada")
        if postulacion.estudiante_id != estudiante_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta postulación")
        return postulacion
