from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


# TODO:根据数据库调整
class ProductionData(Base):
    __tablename__ = "splice_result_splicedata"
    __table_args__ = {"schema": "mims_dev"}

    id: Mapped[int] = mapped_column("ID", primary_key=True)

    sninfoid: Mapped[int] = mapped_column("sninfoid")

    il: Mapped[float | None] = mapped_column("il")

    spliceil: Mapped[float | None] = mapped_column("spliceil")

    leftangle: Mapped[float] = mapped_column("leftangle")

    rightangle: Mapped[float] = mapped_column("rightangle")

    splicecount: Mapped[int] = mapped_column("splicecount")

    production_datetime: Mapped[str | None] = mapped_column("datetime", DateTime)

    splicenumber: Mapped[str] = mapped_column("splicenumber")

    splicemode: Mapped[str | None] = mapped_column("splicingmode")

    pn: Mapped[str] = mapped_column("pn")

    def __repr__(self) -> str:
        return (
            f"ProductionData("
            f"id={self.id}, "
            f"il={self.il}, "
            f"spliceil={self.spliceil}, "
            f"leftangle={self.leftangle}, "
            f"rightangle={self.rightangle}, "
            f"splicenumber={self.splicenumber}, "
            f"splicemode='{self.splicemode}', "
            f"pn='{self.pn}'"
            f")"
        )
