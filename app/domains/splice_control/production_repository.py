"""产线数据访问"""

from collections import defaultdict

from sqlalchemy import select, literal, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.splice_control.models.production_data import \
    ProductionData
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
from sqlalchemy import or_, and_, distinct
from sqlalchemy import ColumnElement
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


class AngleDistributionRow(NamedTuple):
    """切割角度数据分布数据库聚合结果"""

    splicenumber: str
    angle_type: str

    angle_range: str
    angle_count: int
    min_angle: Decimal
    max_angle: Decimal


class ProductionSpliceRepository:
    """产线数据访问"""
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_production_pns(self) -> list[str]:
        """获取产线所有PN"""
        stmt = (
            select(ProductionData.pn)
                .distinct()
                .where(ProductionData.pn.is_not(None), ProductionData.pn != "")
                .order_by(ProductionData.pn)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_production_modes(self) -> list[str]:
        """获取产线所有熔接模式"""
        stmt = (
            select(ProductionData.splicemode)
                .distinct()
                .where(ProductionData.splicemode.is_not(None), ProductionData.splicemode != "")
                .order_by(ProductionData.splicemode)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_pn_modes(self, pn: str) -> list[str]:
        """获取某pn下的熔接模式"""
        stmt = (
            select(ProductionData.splicemode)
                .distinct()
                .where(ProductionData.pn == pn)
                .order_by(ProductionData.splicemode)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_production_splicenumbers(self) -> list[str]:
        """获取所有熔接机编号"""
        stmt = (
            select(ProductionData.splicenumber)
                .distinct()
                .where(ProductionData.splicenumber.is_not(None), ProductionData.splicenumber != "")
                .order_by(ProductionData.splicenumber)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_splicenumber_modes(self, splicenumber: str) -> list[str]:
        """获取某熔接机标号下的熔接模式"""
        stmt = (
            select(ProductionData.splicemode)
                .distinct()
                .where(ProductionData.splicenumber == splicenumber)
                .order_by(ProductionData.splicemode)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_pn_il_distribution(
            self,
            pn: str | None,
            modes: list[str] | None,
            start: date | None,
            end: date | None,
    ):
        """某pn下各熔接模式的IL数据分布"""
        # datetime 兜底:字符串 -> datetime
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        # 熔接数据:spliceil 有有效值就用它,否则回退 il
        loss_value = func.coalesce(
            self.to_num(ProductionData.spliceil),
            self.to_num(ProductionData.il),
        )

        filters = [
            ProductionData.splicemode.is_not(None),
            func.trim(ProductionData.splicemode) != "",
            loss_value.is_not(None),
            loss_value >= 0,
            loss_value <= 1,  # 已保证每个模式的 max 不超过 1
        ]
        if modes:
            filters.append(ProductionData.splicemode.in_(modes))
        if pn:
            filters.append(ProductionData.pn == pn)
        if start is not None:
            filters.append(ProductionData.production_datetime >= start)
        if end is not None:
            filters.append(ProductionData.production_datetime < end)

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

    async def get_pn_qualified_rate(
            self,
            pn: str | None = None,
            modes: list[str] | None = None,
            start: date | None = None,
            end: date | None = None
    ):
        """某pn下各熔接模式的熔接合格率参数(sninfoid个数，splicecount总和)"""
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        filters = [
            ProductionData.splicemode.is_not(None),
            func.trim(ProductionData.splicemode) != "",
        ]
        if pn:
            filters.append(ProductionData.pn == pn)
        if modes:
            filters.append(ProductionData.splicemode.in_(modes))
        if start is not None:
            filters.append(ProductionData.production_datetime >= start)
        if end is not None:
            filters.append(ProductionData.production_datetime < end)

        filtered_qualified = (
            select(
                ProductionData.splicemode.label("splice_mode"),
                ProductionData.sninfoid.label("sninfoid"),
                ProductionData.splicecount.label("splicecount")
            )
                .where(*filters)
                .cte("filtered_qualified")
        )

        stmt = (
            select(
                filtered_qualified.c.splice_mode,
                func.count(
                    filtered_qualified.c.sninfoid
                ).label("sn_count"),
                func.sum(
                    filtered_qualified.c.splicecount
                ).label("splice_count"),
            )
                .group_by(filtered_qualified.c.splice_mode)
        )

        rows = (await self.db.execute(stmt)).all()

        result = []

        for row in rows:
            q_rate = 100 * (row.sn_count / row.splice_count)
            if q_rate == 100:
                q_rate = "100%"
            else:
                q_rate = f"{(100 * (row.sn_count / row.splice_count)):.1f}%"
            result.append(
                QualifiedFactorRow(
                    splice_mode=row.splice_mode,
                    total_sninfoid=row.sn_count,
                    total_splicecount=row.splice_count,
                    qualified_rate=q_rate
                )
            )

        return result

    async def get_splicenumber_qualified_rate(
            self,
            splicenumber: str | None = None,
            modes: list[str] | None = None,
            start: date | None = None,
            end: date | None = None
    ):
        """某熔接机编号下各熔接模式的熔接合格率参数(sninfoid个数，splicecount总和)"""
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        filters = [
            ProductionData.splicemode.is_not(None),
            func.trim(ProductionData.splicemode) != "",
        ]
        if splicenumber:
            filters.append(ProductionData.splicenumber == splicenumber)
        if modes:
            filters.append(ProductionData.splicemode.in_(modes))
        if start is not None:
            filters.append(ProductionData.production_datetime >= start)
        if end is not None:
            filters.append(ProductionData.production_datetime < end)

        filtered_qualified = (
            select(
                ProductionData.splicemode.label("splice_mode"),
                ProductionData.sninfoid.label("sninfoid"),
                ProductionData.splicecount.label("splicecount")
            )
                .where(*filters)
                .cte("filtered_qualified")
        )

        stmt = (
            select(
                filtered_qualified.c.splice_mode,
                func.count(
                    filtered_qualified.c.sninfoid
                ).label("sn_count"),
                func.sum(
                    filtered_qualified.c.splicecount
                ).label("splice_count"),
            )
                .group_by(filtered_qualified.c.splice_mode)
        )

        rows = (await self.db.execute(stmt)).all()

        result = []

        for row in rows:
            q_rate = 100 * (row.sn_count / row.splice_count)
            if q_rate == 100:
                q_rate = "100%"
            else:
                q_rate = f"{(100 * (row.sn_count / row.splice_count)):.1f}%"
            result.append(
                QualifiedFactorRow(
                    splice_mode=row.splice_mode,
                    total_sninfoid=row.sn_count,
                    total_splicecount=row.splice_count,
                    qualified_rate=q_rate
                )
            )

        return result

    from datetime import date, datetime
    from decimal import Decimal

    from sqlalchemy import (
        select,
        func,
        case,
        and_,
        true,
        literal,
        union_all,
    )

    # 请根据你项目中的实际路径导入
    # from app.models.production_data import ProductionData
    # from app.schemas.production_data import AngleDistributionRow

    async def get_splicenumber_angle_distribution(
            self,
            splicenumbers: list[str] | None,
            start: date | datetime | str | None,
            end: date | datetime | str | None,
    ) -> list[AngleDistributionRow]:
        """
        按 splicenumber 统计 leftangle 和 rightangle 的角度分布。

        每个 splicenumber 下：
        1. leftangle 独立按 min 到 max 分成 10 个区间
        2. rightangle 独立按 min 到 max 分成 10 个区间
        3. 没有数据的区间 count 补 0
        """
        if isinstance(start, str):
            start = datetime.fromisoformat(start)

        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        # 将字符串类型的角度安全转换成数值
        left_angle_value = self.to_num(ProductionData.leftangle)
        right_angle_value = self.to_num(ProductionData.rightangle)

        # 公共筛选条件
        common_filters = [
            ProductionData.splicenumber.is_not(None),
            func.trim(ProductionData.splicenumber) != "",
        ]

        if splicenumbers:
            common_filters.append(
                ProductionData.splicenumber.in_(splicenumbers)
            )

        if start is not None:
            common_filters.append(
                ProductionData.production_datetime >= start
            )

        if end is not None:
            common_filters.append(
                ProductionData.production_datetime < end
            )

        # 第一步：筛选 leftangle
        filtered_left_angle = (
            select(
                ProductionData.splicenumber.label("splicenumber"),
                left_angle_value.label("angle"),
                literal("left_angle").label("angle_type"),
            )
                .where(
                *common_filters,
                left_angle_value.is_not(None),
            )
        )

        # 第一步：筛选 rightangle
        filtered_right_angle = (
            select(
                ProductionData.splicenumber.label("splicenumber"),
                right_angle_value.label("angle"),
                literal("right_angle").label("angle_type"),
            )
                .where(
                *common_filters,
                right_angle_value.is_not(None),
            )
        )

        # 合并左右角度，形成统一的数据结构
        filtered_angle = union_all(
            filtered_left_angle,
            filtered_right_angle,
        ).cte("filtered_angle")

        # 第二步：
        # 按 splicenumber + angle_type 分区，
        # 分别计算 leftangle/rightangle 自己的 min 和 max
        bounded = (
            select(
                filtered_angle.c.splicenumber,
                filtered_angle.c.angle_type,
                filtered_angle.c.angle,
                func.min(filtered_angle.c.angle)
                    .over(
                    partition_by=(
                        filtered_angle.c.splicenumber,
                        filtered_angle.c.angle_type,
                    )
                )
                    .label("angle_min"),
                func.max(filtered_angle.c.angle)
                    .over(
                    partition_by=(
                        filtered_angle.c.splicenumber,
                        filtered_angle.c.angle_type,
                    )
                )
                    .label("angle_max"),
            )
                .cte("bounded")
        )

        # 第三步：
        # 每个 splicenumber 下的 left/right angle 独立分成 10 桶
        #
        # width_bucket 对 angle == angle_max 的值可能返回 11，
        # 使用 least(..., 10) 限制到第 10 桶。
        #
        # 如果 angle_max == angle_min，说明所有值相同，
        # 统一放入第 1 桶。
        bucket = case(
            (
                bounded.c.angle_max > bounded.c.angle_min,
                func.least(
                    func.width_bucket(
                        bounded.c.angle,
                        bounded.c.angle_min,
                        bounded.c.angle_max,
                        10,
                    ),
                    10,
                ),
            ),
            else_=1,
        ).label("bucket")

        # 第四步：统计实际有数据的桶
        counted = (
            select(
                bounded.c.splicenumber,
                bounded.c.angle_type,
                bucket,
                func.count().label("count"),
            )
                .group_by(
                bounded.c.splicenumber,
                bounded.c.angle_type,
                bucket,
            )
                .cte("counted")
        )

        # 每个 splicenumber + angle_type 的最小值和最大值
        angle_bounds = (
            select(
                bounded.c.splicenumber,
                bounded.c.angle_type,
                bounded.c.angle_min,
                bounded.c.angle_max,
            )
                .distinct()
                .cte("angle_bounds")
        )

        # 生成 1 到 10 的桶号
        bucket_series = (
            select(
                func.generate_series(1, 10).label("bucket")
            )
                .cte("bucket_series")
        )

        # 骨架：
        # 每个 splicenumber + angle_type × 10 个桶
        skeleton = (
            select(
                angle_bounds.c.splicenumber,
                angle_bounds.c.angle_type,
                angle_bounds.c.angle_min,
                angle_bounds.c.angle_max,
                bucket_series.c.bucket,
            )
                .select_from(
                angle_bounds.join(bucket_series, true())
            )
                .cte("skeleton")
        )

        # 骨架 LEFT JOIN 实际计数，没有数据的桶补 0
        stmt = (
            select(
                skeleton.c.splicenumber,
                skeleton.c.angle_type,
                skeleton.c.bucket,
                func.coalesce(counted.c.count, 0).label("count"),
                skeleton.c.angle_min,
                skeleton.c.angle_max,
            )
                .select_from(
                skeleton.outerjoin(
                    counted,
                    and_(
                        skeleton.c.splicenumber
                        == counted.c.splicenumber,

                        skeleton.c.angle_type
                        == counted.c.angle_type,

                        skeleton.c.bucket
                        == counted.c.bucket,
                    ),
                )
            )
                .order_by(
                skeleton.c.splicenumber,
                skeleton.c.angle_type,
                skeleton.c.bucket,
            )
        )

        rows = (await self.db.execute(stmt)).all()

        # 根据桶号还原角度区间
        result: list[AngleDistributionRow] = []

        for row in rows:
            lo_b = float(row.angle_min)
            hi_b = float(row.angle_max)

            # 正常情况下，每个区间宽度为 (max - min) / 10
            if hi_b > lo_b:
                step = (hi_b - lo_b) / 10

                lo = lo_b + (row.bucket - 1) * step
                hi = lo_b + row.bucket * step
            else:
                # 当前类型的所有角度值完全相同
                lo = lo_b
                hi = hi_b

            result.append(
                AngleDistributionRow(
                    splicenumber=row.splicenumber,
                    angle_range=f"{lo:.4f}~{hi:.4f}",
                    angle_count=int(row.count),
                    max_angle=Decimal(str(hi_b)),
                    min_angle=Decimal(str(lo_b)),
                    angle_type=row.angle_type,
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














