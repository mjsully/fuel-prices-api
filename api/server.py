import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from statistics import mean

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from haversine import haversine
from sqlalchemy import create_engine, func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

import constants
import models


@asynccontextmanager
async def lifespan(app: FastAPI):

    """On application startup, check if DB exists and if not create."""

    initialise()
    yield
    logging.debug("Exiting!")

app = FastAPI(lifespan=lifespan)
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

def initialise():

    """Check if DB exists and if not build the database from the model."""

    if not os.path.exists('data'):
        os.mkdir('data')
    if not os.path.exists(constants.DB_FILEPATH):
        logging.debug('DB does not exist!')
        engine = create_engine(f"sqlite:///{constants.DB_FILEPATH}")
        models.Base.metadata.create_all(engine)
    build_database()

def get_session():

    """Return a session instance."""

    engine = create_engine(f"sqlite:///{constants.DB_FILEPATH}")
    Session = sessionmaker(bind=engine)
    session = Session()
    return session

def calculate_travel_cost(prices, distance, mpg=30):

    results_dict = {}
    for price in prices:
        p = prices[price]
        if not isinstance(p, (str)):
            cost = (p * distance * 4.546)/(mpg * 1.60934 * 100)
            results_dict[price] = round(cost, 2)
    return results_dict

def build_database():

    """Build and populate the database."""

    session = get_session()

    resources = {
        "tesco": "https://www.tesco.com/fuel_prices/fuel_prices_data.json",
        "morrisons": "https://www.morrisons.com/fuel-prices/fuel.json",
        "sainsburys": "https://api.sainsburys.co.uk/v1/exports/latest/fuel_prices_data.json",
        "asda": "https://storelocator.asda.com/fuel_prices_data.json",
        "bp": "https://www.bp.com/en_gb/united-kingdom/home/fuelprices/fuel_prices_data.json",
        "shell": "https://www.shell.co.uk/fuel-prices-data.html",
        "esso": "https://fuelprices.esso.co.uk/latestdata.json"
    }

    headers = {
        "User-Agent": constants.USER_AGENT_HEADERS
    }

    session = get_session()

    for resource in resources:

        res = requests.get(resources[resource], headers=headers)

        if res.status_code == 200:
            data = res.json()
            timestamp = datetime.strptime(data["last_updated"], "%d/%m/%Y %H:%M:%S")
            for site in tqdm(data["stations"]):
                id = None
                try:
                    id = session.execute(
                        insert(models.FuelStations).values(
                            siteid = site["site_id"],
                            name = site["address"],
                            brand = site["brand"],
                            postcode = site["postcode"],
                            latitude = site["location"]["latitude"],
                            longitude = site["location"]["longitude"]
                        ).returning(models.FuelStations.id)
                    )
                    id = id.one()[0]
                    logging.debug(id)
                except SQLAlchemyError as e:
                    # logging.error(e)
                    error = e
                if id is None:
                    try:
                        results = session.query(
                            models.FuelStations
                        ).filter(
                            models.FuelStations.siteid == site["site_id"]
                        ).one()
                        if results:
                            id = results.id
                            logging.debug("Retrieved ID: %s", {id})
                    except SQLAlchemyError as e:
                        # logging.error(e)
                        error = e
                try:
                    fuel_prices = site["prices"]
                    session.execute(
                        insert(models.FuelPrices).values(
                            siteid = id,
                            price_e5 = prices["E5"] if "E5" in fuel_prices.keys() else -1,
                            price_e10 = prices["E10"] if "E10" in fuel_prices.keys() else -1,
                            price_b7 = prices["B7"] if "B7" in fuel_prices.keys() else -1,
                            price_sdv = prices["SDV"] if "SDV" in fuel_prices.keys() else -1,
                            timestamp = timestamp
                        )
                    )
                except Exception as e:
                    # logging.error(e)
                    error = e
    session.commit()
    session.close()

def format_price(price):

    """Simple function for formatting the price when no data is available."""

    if price is not None and price != -1:
        return round(float(price), 2)
    else:
        return constants.NO_DATA_STRING

def get_price(id):

    """Query the DB by station DB id and return the latest prices. """

    session = get_session()
    results = session.query(
        models.FuelPrices
    ).filter(
        models.FuelPrices.siteid == id,
    ).order_by(
        models.FuelPrices.timestamp.desc()
    ).first()
    session.close()
    price_dict = {}
    if results:
        price_dict["e5"] = format_price(results.price_e5)
        price_dict["e10"] = format_price(results.price_e10)
        price_dict["b7"] = format_price(results.price_b7)
        price_dict["sdv"] = format_price(results.price_sdv)
        price_dict["updated"] = results.timestamp.strftime(constants.TIMESTAMP_FORMAT)
    return price_dict

@app.get('/stations')
async def stations():

    """Retrieve data for all stations in the database."""

    session = get_session()

    results = session.query(
        models.FuelStations
    ).all()
    session.close()

    if results:
        results_list = []
        for result in results:
            results_list.append({
                "id": result.id,
                "siteid": result.siteid,
                "name": result.name,
                "brand": result.brand,
                "postcode": result.postcode,
                "latlon": (result.latitude, result.longitude)
            })
        return JSONResponse(status_code=200, content=results_list)
    else:
        return JSONResponse(status_code=404, content="No data.")

@app.get('/stations/nearest')
async def stations_nearest(lat: float, lon: float, distance: int, fueltype: str | None = None):

    """Retrieve data for all stations in the database within a given distance."""

    # INSERT ASSERTION ON FUELTYPE
    if fueltype is not None:
        if fueltype not in ["e5", "e10", "b7", "sdv"]:
            return JSONResponse(
                status_code=400,
                content=constants.FUELTYPE_ERROR_STRING.format(fueltype))

    session = get_session()

    results = session.query(
        models.FuelStations
    ).all()

    if results:
        results_list = []
        for result in results:
            station_coordinates = (result.latitude, result.longitude)
            search_coordinates = (lat, lon)
            dist = haversine(station_coordinates, search_coordinates)
            if dist > distance:
                continue
            else:
                results_list.append({
                    "id": result.id,
                    "siteid": result.siteid,
                    "name": result.name,
                    "brand": result.brand,
                    "postcode": result.postcode,
                    "latlon": (result.latitude, result.longitude),
                    "distance_km": round(dist, 2),
                    "prices": get_price(result.id),
                    "travel_cost_estimate": calculate_travel_cost(get_price(result.id), dist)
                })
        if fueltype is None:
            results_list = sorted(results_list, key = lambda x: x["distance_km"] )
        else:
            results_list = [
                i for i in results_list if i["prices"][fueltype] != constants.NO_DATA_STRING
            ]
            results_list = sorted(results_list, key = lambda x: x["prices"][fueltype])
        return JSONResponse(status_code=200, content=results_list)
    else:
        return JSONResponse(status_code=404, content="No data.")

@app.get('/station/{id}')
async def station_id(id: int):

    """Retrieve data for a given station in the database."""

    session = get_session()

    results = session.query(
        models.FuelStations
    ).filter(
        models.FuelStations.id == id
    ).one()
    session.close()

    if results:
        results_dict = {
            "id": results.id,
            "siteid": results.siteid,
            "name": results.name,
            "brand": results.brand,
            "postcode": results.postcode,
            "latlon": (results.latitude, results.longitude)
        }
        return JSONResponse(status_code=200, content=results_dict)
    else:
        return JSONResponse(status_code=404, content="No data.")

@app.get('/prices')
async def prices():

    """Retrieve all price data for all stations in the database."""

    build_database()

    session = get_session()

    results = session.query(
        models.FuelPrices
    ).all()
    session.close()

    if results:
        results_list = []
        for result in results:
            results_list.append({
                "id": result.id,
                "siteid": result.siteid,
                "price_e5": format_price(result.price_e5),
                "price_e10": format_price(result.price_e10),
                "price_b7": format_price(result.price_b7),
                "price_sdv": format_price(result.price_sdv),
                "timestamp": result.timestamp.strftime(constants.TIMESTAMP_FORMAT)
            })
        return JSONResponse(status_code=200, content=results_list)
    else:
        return JSONResponse(status_code=404, content="No data.")

@app.get('/prices/average')
async def prices_average():

    """Retrieve average price data for all stations in the database."""

    build_database()

    session = get_session()

    e5_results = session.query(
        func.avg(models.FuelPrices.price_e5)
    ).filter(
        models.FuelPrices.price_e5 > 0
    ).one()
    e5_results = round(e5_results[0], 2)
    e10_results = session.query(
        func.avg(models.FuelPrices.price_e10)
    ).filter(
        models.FuelPrices.price_e10 > 0
    ).one()
    e10_results = round(e10_results[0], 2)
    b7_results = session.query(
        func.avg(models.FuelPrices.price_b7)
    ).filter(
        models.FuelPrices.price_b7 > 0
    ).one()
    b7_results = round(b7_results[0], 2)
    sdv_results = session.query(
        func.avg(models.FuelPrices.price_sdv)
    ).filter(
        models.FuelPrices.price_sdv > 0
    ).one()
    sdv_results = round(sdv_results[0], 2)
    session.close()

    if e5_results or e10_results or b7_results or sdv_results:
        results_dict = {
            "price_e5": e5_results,
            "price_e10": e10_results,
            "price_b7": b7_results,
            "price_sdv": sdv_results
        }
        return JSONResponse(status_code=200, content=results_dict)
    else:
        return JSONResponse(status_code=404, content="No data.")

@app.get('/price/{id}')
async def price_id(id: int):

    """Retrieve price data for a given station in the database."""

    build_database()

    session = get_session()

    results = session.query(
        models.FuelPrices
    ).filter(
        models.FuelPrices.siteid == id
    ).order_by(
        models.FuelPrices.timestamp.desc()
    ).first()
    all_results = session.query(
        models.FuelPrices
    ).filter(
        models.FuelPrices.siteid == id
    ).all()
    session.close()

    price_e5_values = [float(i.price_e5) for i in all_results if float(i.price_e5) > 0]
    price_e10_values = [float(i.price_e10) for i in all_results if float(i.price_e10) > 0]
    price_b7_values = [float(i.price_b7) for i in all_results if float(i.price_b7) > 0]
    price_sdv_values = [float(i.price_sdv) for i in all_results if float(i.price_sdv) > 0]

    price_e5_values = [-1] if len(price_e5_values) == 0 else price_e5_values
    price_e10_values = [-1] if len(price_e10_values) == 0 else price_e10_values
    price_b7_values = [-1] if len(price_b7_values) == 0 else price_b7_values
    price_sdv_values = [-1] if len(price_sdv_values) == 0 else price_sdv_values

    if results:
        results_dict = {
            "id": results.id,
            "siteid": results.siteid,
            "price_e5": format_price(results.price_e5),
            "price_e10": format_price(results.price_e10),
            "price_b7": format_price(results.price_b7),
            "price_sdv": format_price(results.price_sdv),
            "price_e5_average": format_price(mean(price_e5_values)),
            "price_e10_average": format_price(mean(price_e10_values)),
            "price_b7_average": format_price(mean(price_b7_values)),
            "price_sdv_average": format_price(mean(price_sdv_values)),
            "timestamp": results.timestamp.strftime(constants.TIMESTAMP_FORMAT)
        }
        return JSONResponse(status_code=200, content=results_dict)
    else:
        return JSONResponse(status_code=404, content="No data.")

@app.get('/database')
async def database():

    """Get database information."""

    session = get_session()

    results_fuel_station = session.query(
        models.FuelStations
    ).all()
    results_fuel_prices = session.query(
        models.FuelPrices
    ).all()
    results_dict = {
        "FuelStations": len(results_fuel_station),
        "FuelPrices": len(results_fuel_prices)
    }
    return JSONResponse(status_code=200, content=results_dict)
