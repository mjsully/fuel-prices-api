import datetime

from sqlalchemy import Column, Integer, Numeric, String, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, column_property, mapped_column, Mapped


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
    siteid = mapped_column(Integer, ForeignKey("fuel_stations.siteid"))
    price_e5 = mapped_column(Numeric)
    price_e10 = mapped_column(Numeric)
    price_b7 = mapped_column(Numeric)
    price_sdv = mapped_column(Numeric)
    timestamp: Mapped[datetime.datetime]


# class SteamAppsMetadata(Base):
#     __tablename__ = "steam_apps_metadata"
#     id: Mapped[int] = mapped_column(primary_key=True)
#     size = mapped_column(Integer)
#     timestamp: Mapped[datetime.datetime]

# class SteamUserApps(Base):
#     __tablename__ = "steam_user_apps"
#     id: Mapped[int] = mapped_column(primary_key=True)
#     appid = mapped_column(Integer, ForeignKey("steam_apps.appid"), unique=True)
#     now_playing: Mapped[int]
#     favourite: Mapped[int]

