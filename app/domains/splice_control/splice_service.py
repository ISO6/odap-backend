"""熔接工艺业务服务。"""

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from decimal import Decimal

from .splice_repository import TestSpliceRepository
from app.shared.cacheable import cacheable

class TestSpliceService:
    """熔接工艺业务服务。"""
    MAX_ALLOWED_IL = Decimal("1.0")

    FIXED_IL_LABELS = [
        "0~0.05",
        "0.05~0.10",
        "0.10~0.15",
        "0.15~0.20",
        "0.20~0.25",
    ]

    def __init__(
        self,
        repository: TestSpliceRepository,
    ):
        self.repository = repository

    @cacheable(key="test_splice_modes")
    async def get_modes(self) -> list[str]:
        # TODO:以后可加Redis缓存、权限检查、数据过滤、日志
        return await self.repository.get_splice_modes()

    async def get_splice_il_distribution(
            self,
            modes: list[str] | None,
            start: date | None,
            end: date | None,
    ) -> dict[str, dict[str, list[str] | list[int]]]:
        """各熔接模式下IL数据分布"""
        start_time = self._to_start_datetime(start)
        end_time = self._to_exclusive_end_datetime(end)

        rows = await self.repository.get_splice_il_distribution(
            modes=modes,
            start=start,
            end=end
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