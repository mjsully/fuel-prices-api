<div>
  <a target="_blank" href="https://github.com/mjsully/fuel-prices-api/actions"><img src="https://github.com/mjsully/fuel-prices-api/actions/workflows/main.yml/badge.svg?event=push" /></a>
  <a target="_blank" href="https://github.com/mjsully/fuel-prices-api/commits/master"><img src="https://img.shields.io/github/last-commit/mjsully/fuel-prices-api" /></a>
</div>

# UK fuel prices API

This repo contains a simple RESTful API for querying the most recent fuel prices for UK stations. The data is taken from [gov.uk](https://www.gov.uk/guidance/access-fuel-price-data). Price data for various fuel station brands are stored in JSON format, which are read by the API and stored in a SQLite database. 

## Deployment

Deployment of this API can be done using Docker. An example docker-compose.yml is given in this repo. 

## API endpoints

There are currently 6 endpoints.

```
/stations/ - returns station data for every fuel station in the database. 
/stations/nearest - requires a latitude, longitude and distance threshold, provided as query parameters (lat, lon, distance). Returns JSON data for all fuel stations within that radius. 
/stations/{id} - returns data for a given fuel station. The ID parameter is the database ID.
/prices/ - returns price data for every fuel station in the database. 
/prices/{id} - returns price data for a given fuel station. The ID parameter is the database ID.
/database/ - returns an audit of the database, containing the number of fuel stations in the database, as well as the number of datapoints in the fuel price table.
```
