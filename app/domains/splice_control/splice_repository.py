"""只负责数据库访问"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.splice_control.models.splice_data import \
    SpliceData
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


class IlDistributionRow(NamedTuple):
    """IL 分布数据库聚合结果。"""

    splice_mode: str
    il_range: str
    count: int
    max_il: Decimal

class TestSpliceRepository:
    """调试工序数据访问"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_splice_modes(self) -> list[str]:
        """获取所有熔接模式"""

        stmt = (
            select(SpliceData.splicemode)
                .distinct()
                .where(SpliceData.splicemode.is_not(None), SpliceData.splicemode != "")
                .order_by(SpliceData.splicemode)
        )

        result = await self.db.execute(stmt)

        return result.scalars().all()

    async def get_splice_il_distribution(
            self,
            modes: list[str] | None,
            start: date | None,
            end: date | None,
    ):
        """各熔接模式下的IL分布"""
        # datetime 兜底:字符串 -> datetime
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        # 熔接数据:spliceil 有有效值就用它,否则回退 il
        loss_value = func.coalesce(
            self.to_num(SpliceData.actual_loss),
        )

        filters = [
            SpliceData.splicemode.is_not(None),
            func.trim(SpliceData.splicemode) != "",
            loss_value.is_not(None),
            loss_value >= 0,
            loss_value <= 1,  # 已保证每个模式的 max 不超过 1
        ]
        if modes:
            filters.append(SpliceData.splicemode.in_(modes))
        if start is not None:
            filters.append(SpliceData.splice_datetime >= start)
        if end is not None:
            filters.append(SpliceData.splice_datetime < end)

        # 第一步:筛选数据
        filtered_il = (
            select(
                SpliceData.splicemode.label("splice_mode"),
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
        # width_bucket 对 == max 的值会返回 11,用 least 夹到 10;
        # 若某模式只有一个值(max==min)会报错,用 case 兜底成第 1 桶。
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
        result = []
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
                    max_il=Decimal(str(hi_b)),  # 该模式自己的 max
                )
            )
        return result

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
