from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


# TODO:根据数据库调整
class SpliceData(Base):
    __tablename__ = "splice_result_adjustdata"
    __table_args__ = {"schema": "mims_dev"}

    id: Mapped[int] = mapped_column("ID", primary_key=True)

    splicemode: Mapped[str | None] = mapped_column("splicingmode")

    actual_loss: Mapped[str | None] = mapped_column("realil")

    actual_loss_limit: Mapped[str | None] = mapped_column("realilmax")

    splice_datetime: Mapped[datetime | None] = mapped_column("datetime", DateTime)

    splice_number: Mapped[str | None] = mapped_column("splicenumber")

    pn: Mapped[str | None] = mapped_column("pn")

    def __repr__(self) -> str:
        return (
            f"SpliceData("
            f"id={self.id}, "
            f"pn='{self.pn}', "
            f"splicemode='{self.splicemode}'"
            f")"
        )
