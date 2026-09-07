"""只负责数据库访问"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.splice_control.models.production_data import ProductionData

from app.infrastructure.database.splice_control.models.tray_data import (
    TrayPN,
    TrayCondition,
    TrayData
)
from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import Numeric
from sqlalchemy import case
from sqlalchemy import cast
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import true
from sqlalchemy import and_
import json
import numpy as np


class IlDistributionRow(NamedTuple):
    """IL 分布数据库聚合结果。"""

    splice_mode: str
    il_range: str
    count: int
    max_il: Decimal


class QualifiedFactorRow(NamedTuple):
    """合格率数据库聚合结果"""

    splice_mode: str
    total_sninfoid: int
    total_splicecount: int
    qualified_rate: str


class PnAndPnidRow(NamedTuple):
    """返回pn聚合结果"""

    pn: str
    pn_id: int


class ConditionsRow(NamedTuple):
    """分段/整段条件"""

    cond_id: int
    port_name_conditions: str


class TrayDataRow(NamedTuple):
    """条件查询的盘盒测试聚合结果"""

    cond_id: int
    value_range: str
    count: int
    max_value: Decimal
    min_value: Decimal


class TrayQualifiedRateRow(NamedTuple):
    """条件查询的盘盒测试合格率聚合结果"""

    cond_id: int
    total: int
    pass_count: int
    qualified_rate: str


class TrayRepository:
    """盘盒测试数据访问"""
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_il_distribution(
        self,
        modes: list[str] | None,
        start: date | None,
        end: date | None,
    ) -> list:
        """各熔接模式的 IL 数据分布"""
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        # 熔接损耗:spliceil 有有效值就用它,否则回退 il
        loss_value = func.coalesce(
            self.to_num(ProductionData.spliceil),
            self.to_num(ProductionData.il),
        )

        filters = self._build_mode_filters(
            modes, start, end,
            extra=[
                loss_value.is_not(None),
                loss_value >= 0,
                loss_value <= 1,  # 已保证每个模式的 max 不超过 1
            ],
        )

        # 第一步:筛选数据
        filtered_il = (
            select(
                ProductionData.splicemode.label("splice_mode"),
                loss_value.label("loss"),
            )
            .where(*filters)
            .cte("filtered_il")
        )

        # 第二步:按 splice_mode 分区,算各自的 min / max
        bounded = (
            select(
                filtered_il.c.splice_mode,
                filtered_il.c.loss,
                func.min(filtered_il.c.loss)
                .over(partition_by=filtered_il.c.splice_mode)
                .label("mode_min"),
                func.max(filtered_il.c.loss)
                .over(partition_by=filtered_il.c.splice_mode)
                .label("mode_max"),
            )
            .cte("bounded")
        )

        # 第三步:每个模式用自己的区间分 10 桶(1~10)
        bucket = case(
            (
                bounded.c.mode_max > bounded.c.mode_min,
                func.least(
                    func.width_bucket(
                        bounded.c.loss,
                        bounded.c.mode_min,
                        bounded.c.mode_max,
                        10,
                    ),
                    10,
                ),
            ),
            else_=1,
        ).label("bucket")

        # 第四步:实际计数(只含有数据的桶)
        counted = (
            select(
                bounded.c.splice_mode,
                bucket,
                func.count().label("count"),
            )
            .group_by(bounded.c.splice_mode, bucket)
            .cte("counted")
        )

        # 每个模式的 min/max(每个模式一行)
        mode_bounds = (
            select(
                bounded.c.splice_mode,
                bounded.c.mode_min,
                bounded.c.mode_max,
            )
            .distinct()
            .cte("mode_bounds")
        )

        # 生成 1~10 的桶号
        bucket_series = (
            select(
                func.generate_series(1, 10).label("bucket")
            )
            .cte("bucket_series")
        )

        # 骨架:每个模式 × 10 个桶(CROSS JOIN)
        skeleton = (
            select(
                mode_bounds.c.splice_mode,
                mode_bounds.c.mode_min,
                mode_bounds.c.mode_max,
                bucket_series.c.bucket,
            )
            .select_from(mode_bounds.join(bucket_series, true()))
            .cte("skeleton")
        )

        # 骨架 LEFT JOIN 实际计数,空桶补 0
        stmt = (
            select(
                skeleton.c.splice_mode,
                skeleton.c.bucket,
                func.coalesce(counted.c.count, 0).label("count"),
                skeleton.c.mode_min,
                skeleton.c.mode_max,
            )
            .select_from(
                skeleton.outerjoin(
                    counted,
                    and_(
                        skeleton.c.splice_mode == counted.c.splice_mode,
                        skeleton.c.bucket == counted.c.bucket,
                    ),
                )
            )
            .order_by(skeleton.c.splice_mode, skeleton.c.bucket)
        )

        rows = (await self.db.execute(stmt)).all()

        # 在 Python 里根据 bucket 序号还原区间标签
        result: list[IlDistributionRow] = []
        for row in rows:
            lo_b = float(row.mode_min)
            hi_b = float(row.mode_max)
            step = (hi_b - lo_b) / 10
            lo = lo_b + (row.bucket - 1) * step
            hi = lo_b + row.bucket * step
            result.append(
                IlDistributionRow(
                    splice_mode=row.splice_mode,
                    il_range=f"{lo:.4f}~{hi:.4f}",
                    count=int(row.count),
                    max_il=Decimal(str(hi_b)),
                )
            )
        return result

    async def get_qualified_rate(
        self,
        modes: list[str] | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list:
        """各熔接模式的合格率参数(sninfoid 个数, splicecount 总和)"""
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        filters = self._build_mode_filters(modes, start, end)

        filtered_qualified = (
            select(
                ProductionData.splicemode.label("splice_mode"),
                ProductionData.sninfoid.label("sninfoid"),
                ProductionData.splicecount.label("splicecount"),
            )
            .where(*filters)
            .cte("filtered_qualified")
        )

        stmt = (
            select(
                filtered_qualified.c.splice_mode,
                func.count(filtered_qualified.c.sninfoid).label("sn_count"),
                func.sum(filtered_qualified.c.splicecount).label("splice_count"),
            )
            .group_by(filtered_qualified.c.splice_mode)
        )

        rows = (await self.db.execute(stmt)).all()

        result: list[QualifiedFactorRow] = []
        for row in rows:
            # 防止除零
            if not row.splice_count:
                q_rate = "0%"
            else:
                rate = 100 * (row.sn_count / row.splice_count)
                q_rate = "100%" if rate == 100 else f"{rate:.1f}%"

            result.append(
                QualifiedFactorRow(
                    splice_mode=row.splice_mode,
                    total_sninfoid=row.sn_count,
                    total_splicecount=row.splice_count,
                    qualified_rate=q_rate,
                )
            )
        return result

    async def get_tray_pns(self) -> list[PnAndPnidRow]:
        """获取所有盘盒盒测试PN"""
        filters = [
            TrayPN.pn.is_not(None), TrayPN.pn != "",
            TrayPN.pn_id.in_(
                select(TrayCondition.pn_id).distinct()
            )
        ]

        stmt = (
            select(
                TrayPN.pn,
                TrayPN.pn_id
            ).distinct()
                .where(*filters)
                .order_by(TrayPN.pn)
        )

        rows = (await self.db.execute(stmt)).all()

        result: list[QualifiedFactorRow] = []

        for row in rows:
            result.append(
                PnAndPnidRow(
                    pn=row.pn,
                    pn_id=row.pn_id
                )
            )

        return result

    async def get_segment_conditions(
            self,
            pn_id: int,
            is_segment: bool
    ) -> list[ConditionsRow]:
        """指定pn_id下的分段/整段条件"""
        filters = [
            TrayCondition.pn_id == pn_id,
        ]

        if is_segment:
            filters.append(
                ~TrayCondition.port_name.contains("FullPath")
            )
        else:
            filters.append(
                TrayCondition.port_name.contains("FullPath")
            )

        stmt = (
            select(
                TrayCondition.cond_id,
                TrayCondition.port_name,
                TrayCondition.conditions
            ).where(*filters)
        )

        rows = (await self.db.execute(stmt)).all()
        result: list[ConditionsRow] = []
        for row in rows:
            port_name_conditions = f"{row.port_name}, {self.json_to_text(row.conditions)}"
            result.append(
                ConditionsRow(
                    cond_id=row.cond_id,
                    port_name_conditions=port_name_conditions
                )
            )
        return result

    async def get_tray_value_distribution(
            self,
            cond_ids: list[int] | None,
            start: date | None,
            end: date | None,
    ) -> dict:
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        filters = self._build_tray_filters(cond_ids, start, end)

        # 只保留落在规格区间内的值,越界(含大负数)直接排除
        filters.append(TrayData.test_value >= TrayData.lsl)
        filters.append(TrayData.test_value <= TrayData.usl)

        filtered = (
            select(
                TrayData.cond_id.label("cond_id"),
                TrayData.test_value.label("test_value"),
                TrayData.lsl.label("lsl"),
                TrayData.usl.label("usl"),
            )
                .where(*filters)
                .cte("filtered")
        )

        # 分桶:边界固定用 lsl/usl,== usl 的值 width_bucket 返回 11,用 least 夹到 10
        bucket = case(
            (
                filtered.c.usl > filtered.c.lsl,
                func.least(
                    func.width_bucket(
                        filtered.c.test_value,
                        filtered.c.lsl,
                        filtered.c.usl,
                        10,
                    ),
                    10,
                ),
            ),
            else_=1,
        ).label("bucket")

        counted = (
            select(
                filtered.c.cond_id,
                bucket,
                func.count().label("count"),
            )
                .group_by(filtered.c.cond_id, bucket)
                .cte("counted")
        )

        # 每个 cond_id 的固定 lsl/usl(一行)
        cond_bounds = (
            select(
                filtered.c.cond_id,
                func.min(filtered.c.lsl).label('lsl'),
                func.max(filtered.c.usl).label('usl'),
            )
                .group_by(filtered.c.cond_id)
                .cte("cond_bounds")
        )

        bucket_series = (
            select(func.generate_series(1, 10).label("bucket"))
                .cte("bucket_series")
        )

        skeleton = (
            select(
                cond_bounds.c.cond_id,
                cond_bounds.c.lsl,
                cond_bounds.c.usl,
                bucket_series.c.bucket,
            )
                .select_from(cond_bounds.join(bucket_series, true()))
                .cte("skeleton")
        )

        stmt = (
            select(
                skeleton.c.cond_id,
                skeleton.c.bucket,
                func.coalesce(counted.c.count, 0).label("count"),
                skeleton.c.lsl,
                skeleton.c.usl,
            )
                .select_from(
                skeleton.outerjoin(
                    counted,
                    and_(
                        skeleton.c.cond_id == counted.c.cond_id,
                        skeleton.c.bucket == counted.c.bucket,
                    ),
                )
            )
                .order_by(skeleton.c.cond_id, skeleton.c.bucket)
        )

        rows = (await self.db.execute(stmt)).all()

        # 标签:直接用 lsl/usl 均分,永远不会出现负数(除非 lsl 本身是负)
        result = []
        for row in rows:
            lo_b = float(row.lsl)  # ← 用 lsl,不用 min()
            hi_b = float(row.usl)  # ← 用 usl,不用 max()
            step = (hi_b - lo_b) / 10
            lo = lo_b + (row.bucket - 1) * step
            hi = lo_b + row.bucket * step

            # Python 里还原区间标签
            result.append(
                TrayDataRow(
                    cond_id=row.cond_id,
                    value_range=f"{lo:.4f}~{hi:.4f}",
                    count=int(row.count),
                    max_value=Decimal(str(hi_b)),
                    min_value=Decimal(str(lo_b)),
                )
            )
        return result

    async def get_tray_qualified_rate(
        self,
        cond_ids: list[int] | None,
        start: date | None,
        end: date | None,
    ):
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        filters = self._build_tray_filters(cond_ids, start, end)

        stmt = (
            select(
                TrayData.cond_id.label("cond_id"),
                func.count().label("total"),
                func.sum(
                    case((TrayData.passfail.is_(True), 1), else_=0)
                ).label("pass_count"),
            )
            .where(*filters)
            .group_by(TrayData.cond_id)
            .order_by(TrayData.cond_id)
        )

        rows = (await self.db.execute(stmt)).all()

        result: list[dict] = []
        for row in rows:
            total = int(row.total or 0)
            pass_count = int(row.pass_count or 0)

            if total == 0:
                rate = "0%"
            else:
                r = 100 * pass_count / total
                rate = "100%" if r == 100 else f"{r:.1f}%"

            result.append(
                TrayQualifiedRateRow(
                    cond_id=row.cond_id,
                    total=total,
                    pass_count=pass_count,
                    qualified_rate=rate
                )
            )
        return result

    # ---------------------------------------------------------
    # Utils
    # ---------------------------------------------------------
    @staticmethod
    def _build_mode_filters(
            modes: list[str] | None,
            start: datetime | None,
            end: datetime | None,
            extra: list | None = None,
    ) -> list:
        """构造按 splicemode 查询的公共过滤条件"""
        filters = [
            ProductionData.splicemode.is_not(None),
            func.trim(ProductionData.splicemode) != "",
        ]
        if modes:
            filters.append(ProductionData.splicemode.in_(modes))
        if start is not None:
            filters.append(ProductionData.production_datetime >= start)
        if end is not None:
            filters.append(ProductionData.production_datetime < end)
        if extra:
            filters.extend(extra)
        return filters

    @staticmethod
    def to_num(col):
        """文本列 -> Numeric;为空/空串/非法数字则返回 NULL。"""
        _NUM_RE = r"^[0-9]+([.][0-9]+)?$"
        t = func.trim(col)
        return case(
            (
                and_(col.is_not(None), t != "", t.op("~")(_NUM_RE)),
                cast(t, Numeric(10, 4)),
            ),
            else_=None,
        )

    @staticmethod
    def json_to_text(data):
        if not data:
            return ''

        if isinstance(data, str):
            data = json.loads(data)

        if isinstance(data, dict):
            return ', '.join(
                f'{k}:{v}'
                for k, v in data.items()
            )

        if isinstance(data, list):
            result = []

            for item in data:
                if isinstance(item, dict):
                    result.append(
                        ', '.join(
                            f'{k}:{v}'
                            for k, v in item.items()
                        )
                    )
                else:
                    result.append(str(item))

            return '; '.join(result)

        return str(data)

    @staticmethod
    def _build_tray_filters(
        cond_ids: list[int] | None,
        start: datetime | None,
        end: datetime | None,
    ) -> list:
        filters = [
            TrayData.lsl.is_not(None),
            TrayData.usl.is_not(None),
            TrayData.test_value.is_not(None),
            TrayData.para_id == 19,
        ]
        if cond_ids:
            filters.append(TrayData.cond_id.in_(cond_ids))
        if start is not None:
            filters.append(TrayData.test_time >= start)
        if end is not None:
            filters.append(TrayData.test_time < end)
        return filters




















