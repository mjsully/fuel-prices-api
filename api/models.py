import datetime

from sqlalchemy import Integer, Numeric, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base(DeclarativeBase):
    pass

class FuelStations(Base):
    __tablename__ = "fuel_stations"
    id: Mapped[int] = mapped_column(primary_key=True)
    siteid = mapped_column(String, unique=True)
    name: Mapped[str]
    brand: Mapped[str]
    postcode: Mapped[str]
    latitude: Mapped[float]
    longitude: Mapped[float]

class FuelPrices(Base):

    __tablename__ = "fuel_prices"
    __table_args__ = (
        UniqueConstraint(
            "siteid",    
            "timestamp",
            name = "fuel_prices_unique_constraint"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    siteid = mapped_column(Integer, ForeignKey("fuel_stations.id"), nullable=False)
    price_e5 = mapped_column(Numeric)
    price_e10 = mapped_column(Numeric)
    price_b7 = mapped_column(Numeric)
    price_sdv = mapped_column(Numeric)
    timestamp: Mapped[datetime.datetime]