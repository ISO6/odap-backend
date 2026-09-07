"""接口"""
from fastapi import APIRouter, Depends, Query
from app.shared.responses import success_response, failure_response
from .splice_service import TestSpliceService
from .production_service import ProductionSpliceService
from .tray_service import TrayService
from app.dependencies.splice_control import (
    get_test_splice_service,
    get_production_service,
    get_tray_service
)
from datetime import date

router = APIRouter(
    prefix="/splice-control",
    tags=["splice-control"],
)


# ---------------------------------------------------------
# 熔接机测试
# ---------------------------------------------------------
@router.get("/test/modes")
async def test_modes(service: TestSpliceService = Depends(get_test_splice_service)):
    """获取所有的熔接模式"""
    modes = await service.get_modes()
    return success_response(item=modes, total=len(modes))


@router.get("/test/splice-il-distribution")
async def test_splice_il_distribution(
    modes: list[str] | None = Query(default=None),
    start: date | None = None,
    end: date | None = None,
    service: TestSpliceService = Depends(
        get_test_splice_service
    ),
):
    """
    每个熔接模式下 IL 分布
    """

    result = await service.get_splice_il_distribution(
        modes=modes,
        start=start,
        end=end,
    )

    return success_response(
        item=result,
        total=len(result),
    )


# ---------------------------------------------------------
# 产线熔接数据
# ---------------------------------------------------------
@router.get("/production/pns")
async def production_pns(service: ProductionSpliceService = Depends(get_production_service)):
    """获取产线所有pn"""
    pns = await service.get_pns()
    return success_response(item=pns, total=len(pns))


@router.get("/production/modes")
async def production_modes(service: ProductionSpliceService = Depends(get_production_service)):
    """获取产线所有的熔接模式"""
    modes = await service.get_modes()
    return success_response(item=modes, total=len(modes))


@router.get("/production/pn-modes")
async def production_pn_modes(
        pn: str | None = None,
        service: ProductionSpliceService = Depends(get_production_service)
):
    """某pn下的所有熔接模式"""
    pn_mode = await service.get_pn_modes(pn)
    return success_response(item=pn_mode, total=len(pn_mode))


@router.get("/production/splicenumbers")
async def production_splicenumbers(service: ProductionSpliceService = Depends(get_production_service)):
    """获取产线所有熔接机编号"""
    splicenumbers = await service.get_splicenumbers()
    return success_response(item=splicenumbers, total=len(splicenumbers))


@router.get("/production/splicenumber-modes")
async def production_splicenumber_modes(
        splicenumber: str | None = None,
        service: ProductionSpliceService = Depends(get_production_service)
):
    """某熔接机编号下的所有熔接模式"""
    splicenumber_modes = await service.get_splicenumber_modes(splicenumber)
    return success_response(item=splicenumber_modes, total=len(splicenumber_modes))


@router.get("/production/pn-il-distribution")
async def pn_il_distribution(
        pn: str | None = None,
        modes: list[str] | None = Query(default=None),
        start: date | None = None,
        end: date | None = None,
        service: ProductionSpliceService = Depends(get_production_service)
):
    """某pn下各熔接模式的IL数据分布"""
    result = await service.get_pn_il_distribution(
        pn=pn,
        modes=modes,
        start=start,
        end=end
    )
    return success_response(item=result, total=len(result))


@router.get("/production/pn-qualified-rate")
async def pn_qualified_rate(
        pn: str | None = None,
        modes: list[str] | None = Query(default=None),
        start: date | None = None,
        end: date | None = None,
        service: ProductionSpliceService = Depends(get_production_service)
):
    """某pn下各熔接模式的合格率"""
    result = await service.get_pn_qualified_rate(
        pn=pn,
        modes=modes,
        start=start,
        end=end
    )
    return success_response(item=result, total=len(result))


@router.get("/production/splicenumber-qualified-rate")
async def splicenumber_qualified_rate(
        splicenumber: str | None = None,
        modes: list[str] | None = Query(default=None),
        start: date | None = None,
        end: date | None = None,
        service: ProductionSpliceService = Depends(get_production_service)
):
    """某熔接机编号下各熔接模式的合格率"""
    result = await service.get_splicenumber_qualified_rate(
        splicenumber=splicenumber,
        modes=modes,
        start=start,
        end=end
    )
    return success_response(item=result, total=len(result))


@router.get("/production/splicenumber-angle-distribution")
async def splicenumber_angle_distribution(
        splicenumbers: list[str] | None = Query(default=None),
        start: date | None = None,
        end: date | None = None,
        service: ProductionSpliceService = Depends(get_production_service)
):
    """指定熔接机编号下切割角度的数据分布"""
    result = await service.get_splicenumber_angle_distribution(
        splicenumbers=splicenumbers,
        start=start,
        end=end
    )
    return success_response(item=result, total=len(result))


# ---------------------------------------------------------
# 盘盒测试数据
# ---------------------------------------------------------
@router.get("/tray/mode-il-distribution-qualified-rate")
async def mode_distribution_and_qualified_rate(
        modes: list[str] | None = Query(default=None),
        start: date | None = None,
        end: date | None = None,
        service: TrayService = Depends(get_tray_service)
):
    """制动熔接模式下熔接数据分布和合格率"""
    result = await service.get_mode_distribution_and_qualified_rate(
        modes=modes,
        start=start,
        end=end
    )
    return success_response(item=result, total=len(result))


@router.get("/tray/pns")
async def tray_pns(service: TrayService = Depends(get_tray_service)):
    """获取盘盒测试所有pn"""
    result = await service.get_tray_pns()
    return success_response(item=result, total=len(result))


@router.get("/tray/segment-conditions")
async def tray_pn_conditions(
        pn_id: int,
        is_segment: bool,
        service: TrayService = Depends(get_tray_service)
):
    """某pn对应的分段/整段测试条件"""
    result = await service.get_segment_conditions(pn_id, is_segment)
    return success_response(item=result, total=len(result))


@router.get("/tray/tray-record")
async def tray_record(
        cond_ids: list[int] | None = Query(default=None),
        start: date | None = None,
        end: date | None = None,
        service: TrayService = Depends(get_tray_service)
):
    """指定条件下的盘盒测试数据"""
    result = await service.get_tray_records(
        cond_ids=cond_ids,
        start=start,
        end=end
    )
    return success_response(item=result, total=len(result))
