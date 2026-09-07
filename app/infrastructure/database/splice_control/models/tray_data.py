from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# TODO:根据数据库修改
class TrayPN(Base):
    """盘盒测试的PN"""
    __tablename__ = "prod_pn_info"

    pn_id: Mapped[int] = mapped_column("pn_id", primary_key=True)

    pn: Mapped[str] = mapped_column("pn")

    def __repr__(self):
        return (
            f"TrayPN("
            f"pn_id={self.pn_id}, "
            f"pn={self.pn}"
            f")"
        )


class TrayCondition(Base):
    """分段+测试条件"""
    __tablename__ = "prod_cond_segment"

    cond_id: Mapped[int] = mapped_column("cond_id", primary_key=True)

    pn_id: Mapped[int] = mapped_column("pn_id")

    port_name: Mapped[str] = mapped_column("port_name")

    conditions: Mapped[str] = mapped_column("conditions")

    def __repr__(self):
        return (
            f"TrayCondition("
            f"cond_id={self.cond_id}, "
            f"pn_id={self.pn_id}, "
            f"port_name='{self.port_name}', "
            f"conditions='{self.conditions}'"
            f")"
        )


class TrayData(Base):
    """盘盒测试数据"""
    __tablename__ = "prod_test_records"

    rec_id: Mapped[int] = mapped_column("rec_id", primary_key=True)

    cond_id: Mapped[int] = mapped_column("cond_id")

    test_value: Mapped[float] = mapped_column("test_value")

    lsl: Mapped[float] = mapped_column("lsl")

    usl: Mapped[float] = mapped_column("usl")

    passfail: Mapped[bool] = mapped_column("passfail")

    para_id: Mapped[int] = mapped_column("para_id")     # default: para_id = 19

    test_time: Mapped[str] = mapped_column("test_time", DateTime)

    def __repr__(self):
        return (
            f"TrayData("
            f"cond_id={self.cond_id}, "
            f"test_value={self.test_time}, "
            f"lsl={self.lsl}, "
            f"usl={self.usl}, "
            f"passfail={self.passfail}, "
            f"test_time={self.test_time}"
            f")"
        )
