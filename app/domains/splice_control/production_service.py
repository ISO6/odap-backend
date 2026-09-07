"""产线熔接数据业务"""

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from decimal import Decimal

from .production_repository import ProductionSpliceRepository
from app.shared.cacheable import cacheable


class ProductionSpliceService:
    """产线熔接数据业务"""
    MAX_ALLOWED_IL = Decimal("1.0")

    def __init__(
        self,
        repository: ProductionSpliceRepository
    ):
        self.repository = repository

    @cacheable(key="production_pns")
    async def get_pns(self) -> list[str]:
        """产线所有pn"""
        return await self.repository.get_production_pns()

    @cacheable(key="production_modes")
    async def get_modes(self) -> list[str]:
        """产线所有熔接模式"""
        return await self.repository.get_production_modes()

    async def get_pn_modes(self, pn: str) -> list[str]:
        """某pn下的所有熔接模式"""
        return await self.repository.get_pn_modes(pn)

    @cacheable(key="production_splicenumbers")
    async def get_splicenumbers(self) -> list[str]:
        """产线所有熔接机编号"""
        return await self.repository.get_production_splicenumbers()

    async def get_splicenumber_modes(self, splicenumber: str) -> list[str]:
        """某熔接机编号下的所有熔接模式"""
        return await self.repository.get_splicenumber_modes(splicenumber)

    async def get_pn_il_distribution(
            self,
            pn: str | None,
            modes: list[str] | None,
            start: date | None,
            end: date | None,
    ) -> dict[str, dict[str, list[str] | list[int]]]:
        """某pn下各熔接模式的IL数据分布"""
        start_time = self._to_start_datetime(start)
        end_time = self._to_exclusive_end_datetime(end)

        rows = await self.repository.get_pn_il_distribution(
            pn=pn,
            modes=modes,
            start=start_time,
            end=end_time
        )

        result: dict[str, dict[str, list[str] | list[int]]] = {}

        if modes:
            for mode in modes:
                result[mode] = {'x': [], 'y': []}

        for row in rows:
            if row.splice_mode not in result:
                result[row.splice_mode] = {'x': [], 'y': []}
            result[row.splice_mode]['x'].append(row.il_range)
            result[row.splice_mode]['y'].append(row.count)
        return result

    async def get_pn_qualified_rate(
            self,
            pn: str | None,
            modes: list[str] | None,
            start: date | None,
            end: date | None
    ) -> dict[str, dict[str, list[str] | list[int]]]:
        """某pn下各熔接模式合格率"""
        start_time = self._to_start_datetime(start)
        end_time = self._to_exclusive_end_datetime(end)

        rows = await self.repository.get_pn_qualified_rate(
            pn=pn,
            modes=modes,
            start=start_time,
            end=end_time
        )

        result: dict[str, dict[str, list[str] | list[int]]] = {pn: {'x': [], 'y': []}}

        for row in rows:
            if row.splice_mode not in result[pn]['x']:
                result[pn]['x'].append(row.splice_mode)
                result[pn]['y'].append(row.qualified_rate)
        return result

    async def get_splicenumber_qualified_rate(
            self,
            splicenumber: str | None,
            modes: list[str] | None,
            start: date | None,
            end: date | None
    ) -> dict[str, dict[str, list[str] | list[int]]]:
        """某熔接机编号下各熔接模式合格率"""
        start_time = self._to_start_datetime(start)
        end_time = self._to_exclusive_end_datetime(end)

        rows = await self.repository.get_splicenumber_qualified_rate(
            splicenumber=splicenumber,
            modes=modes,
            start=start_time,
            end=end_time
        )

        result: dict[str, dict[str, list[str] | list[int]]] = {splicenumber: {'x': [], 'y': []}}

        for row in rows:
            if row.splice_mode not in result[splicenumber]['x']:
                result[splicenumber]['x'].append(row.splice_mode)
                result[splicenumber]['y'].append(row.qualified_rate)
        return result

    async def get_splicenumber_angle_distribution(
            self,
            splicenumbers: list[str] | None,
            start: date | None,
            end: date | None
    ) -> dict[str, dict[str, list[str] | list[int]]]:
        """指定熔接机编号的切割角度数据分布"""
        start_time = self._to_start_datetime(start)
        end_time = self._to_exclusive_end_datetime(end)

        rows = await self.repository.get_splicenumber_angle_distribution(
            splicenumbers=splicenumbers,
            start=start_time,
            end=end_time
        )

        result: dict[str, dict[str, list[str] | list[int]]] = {}

        if splicenumbers:
            for splicenumber in splicenumbers:
                result[splicenumber] = {
                    'left_angle': {
                        'x': [], 'y': []
                    },
                    'right_angle': {
                        'x': [], 'y': []
                    }
                }

        for row in rows:
            if row.splicenumber not in result:
                result[splicenumber] = {
                    'left_angle': {
                        'x': [], 'y': []
                    },
                    'right_angle': {
                        'x': [], 'y': []
                    }
                }
            if row.angle_type == 'left_angle':
                result[row.splicenumber]['left_angle']['x'].append(row.angle_range)
                result[row.splicenumber]['left_angle']['y'].append(row.angle_count)
            if row.angle_type == 'right_angle':
                result[row.splicenumber]['right_angle']['x'].append(row.angle_range)
                result[row.splicenumber]['right_angle']['y'].append(row.angle_count)

        return result

    # ---------------------------------------------------------
    # Utils
    # ---------------------------------------------------------
    @staticmethod
    def _to_start_datetime(
            value: date | None,
    ) -> datetime | None:
        """将开始日期转换成当天 00:00:00。"""

        if value is None:
            return None

        return datetime.combine(
            value,
            time.min,
        )

    @staticmethod
    def _to_exclusive_end_datetime(
            value: date | None,
    ) -> datetime | None:
        """
        将结束日期转换成下一天 00:00:00。

        例如：
        end = 2023-09-27
        转换为：
        splice_datetime < 2023-09-28 00:00:00
        这样可以包含 2023-09-27 全天的数据。
        """

        if value is None:
            return None

        return datetime.combine(
            value + timedelta(days=1),
            time.min,
        )

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        """
        将 Decimal 转成适合前端显示的字符串。

        示例：

        Decimal("0.7000") -> "0.7"
        Decimal("0.7250") -> "0.725"
        Decimal("1.0000") -> "1"
        """

        formatted = format(
            value,
            "f",
        ).rstrip("0").rstrip(".")

        return formatted or "0"
















