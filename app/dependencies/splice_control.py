from fastapi import Depends

from app.infrastructure.database.splice_control.session import get_session

from app.domains.splice_control.splice_repository import TestSpliceRepository
from app.domains.splice_control.splice_service import TestSpliceService

from app.domains.splice_control.production_repository import ProductionSpliceRepository
from app.domains.splice_control.production_service import ProductionSpliceService

from app.domains.splice_control.tray_repository import TrayRepository
from app.domains.splice_control.tray_service import TrayService


def get_test_splice_service(
    db=Depends(get_session)
):
    repository = TestSpliceRepository(db)
    return TestSpliceService(repository)


def get_production_service(
        db=Depends(get_session)
):
    repository = ProductionSpliceRepository(db)
    return ProductionSpliceService(repository)


def get_tray_service(
        db=Depends(get_session)
):
    repository = TrayRepository(db)
    return TrayService(repository)
