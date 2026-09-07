"""盘盒测试数据业务"""

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from decimal import Decimal

import numpy as np

from .tray_repository import TrayRepository
from app.shared.cacheable import cacheable
import pandas as pd


class TrayService:
    """盘盒测试数据业务"""
    MAX_ALLOWED_IL = Decimal("1.0")

    def __init__(
            self,
            repository: TrayRepository
    ):
        self.repository = repository

    async def get_mode_distribution_and_qualified_rate(
            self,
            modes: list[str] | None,
            start: date | None,
            end: date | None
    ):
        """指定熔接模式下的熔接数据分布和合格率"""
        start_time = self._to_start_datetime(start)
        end_time = self._to_exclusive_end_datetime(end)

        if not modes:
            modes = ["HI-CL", "FX-HI"]

        il_rows = await self.repository.get_il_distribution(modes, start_time, end_time)
        qualified_rows = await self.repository.get_qualified_rate(modes, start_time, end_time)

        result: dict[str, dict[str, list[str] | list[int]]] = {}

        if modes:
            for mode in modes:
                result[mode] = {'x': [], 'y': [], 'qualified_rate': str}

        for row in qualified_rows:
            result[row.splice_mode]['qualified_rate'] = row.qualified_rate

        for row in il_rows:
            result[row.splice_mode]['x'].append(row.il_range)
            result[row.splice_mode]['y'].append(row.count)
        return result

    @cacheable(key="tray_pns")
    async def get_tray_pns(self) -> dict:
        """盘盒测试所有pn"""
        rows = await self.repository.get_tray_pns()

        result: dict[str, dict[str, list[str] | list[int]]] = {}

        for row in rows:
            result[row.pn] = row.pn_id

        return result

    async def get_segment_conditions(
            self,
            pn_id: int,
            is_segment: bool
    ) -> dict:
        """某pn对应的分段/整段+测试条件"""
        rows = await self.repository.get_segment_conditions(pn_id, is_segment)

        result: dict[str, dict[str, list[str] | list[int]]] = {}

        for row in rows:
            result[row.port_name_conditions] = row.cond_id
        return result

    async def get_tray_records(
            self,
            cond_ids: list[int] | None,
            start: date | None = None,
            end: date | None = None
    ):
        """指定条件下的盘盒测试数据"""
        start_time = self._to_start_datetime(start)
        end_time = self._to_exclusive_end_datetime(end)

        value_rows = await self.repository.get_tray_value_distribution(cond_ids, start_time, end_time)
        qualified_rows = await self.repository.get_tray_qualified_rate(cond_ids, start_time, end_time)

        result: dict[str, dict[str, list[str] | list[int]]] = {}

        if cond_ids:
            for cond_id in cond_ids:
                result[cond_id] = {'x': [], 'y': [], 'qualified_rate': str}

        for row in qualified_rows:
            result[row.cond_id]['qualified_rate'] = row.qualified_rate

        for row in value_rows:
            result[row.cond_id]['x'].append(row.value_range)
            result[row.cond_id]['y'].append(row.count)
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





