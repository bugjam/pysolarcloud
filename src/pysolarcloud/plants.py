from datetime import datetime, timedelta
from . import AbstractAuth, PySolarCloudException, _LOGGER

class Plants:
    """Class to interact with the plants API."""

    def __init__(self, auth: AbstractAuth, *, lang: str = "_en_US"):
        """Initialize the plants."""
        self.auth = auth
        self.lang = lang

    async def async_get_plants(self) -> list[dict]:
        """Return the list of plants accessible to the user."""
        uri = "/openapi/platform/queryPowerStationList"
        res = await self.auth.request(uri, {"page": 1, "size": 100})
        res.raise_for_status()
        data = await res.json()
        if "error" in data:
            _LOGGER.error("Error response from %s: %s", uri, data)
            raise PySolarCloudException(res)
        plants = [plant for plant in data["result_data"]["pageList"]]
        _LOGGER.debug("async_get_plants: %s", plants)
        return plants

    async def async_get_plant_details(self, plant_id: str | list[str]) -> list[dict]:
        """Return details about one or more plants."""
        if isinstance(plant_id, list):
            ps = ",".join(plant_id)
        else:
            ps = plant_id
        uri = "/openapi/platform/getPowerStationDetail"
        res = await self.auth.request(uri, {"ps_ids": ps})
        data = await res.json()
        if "error" in data:
            _LOGGER.error("Error response from %s: %s", uri, res)
            raise PySolarCloudException(res)
        plants = data["result_data"]["data_list"]
        _LOGGER.debug("async_get_plant_details: %s", plants)
        return plants

    async def async_get_realtime_data(self, plant_id: str | list[str], *, measure_points=None) -> dict:
        """Return the latest realtime data from one or more plants.
        
        plant_id: str | list[str] - The ID of the plant or a list of plant IDs.
        measure_points: list[str] - A list of measure points to return. If None, all measure points are returned.
        Data is returned as a dictionary of dictionaries:
        {
            plant_id: {
                measure_point_code: {
                    "id": str, # Numerical identifier of the measure point
                    "code": str, # Readable code of the measure point (see measure_points dict)
                    "value": float | str,
                    "unit": str,
                    "name": str, # Name of the measure point (in the specified language)
                }
            }
        }
        iSolarCloud data is updated every 5 minutes so polling more frequently than that is not useful.
        """
        if isinstance(plant_id, list):
            ps = plant_id
        else:
            ps = [plant_id]
        if measure_points is None:
            ms = list(self.measure_points.keys())
        else:
            measure_points_map = {v: k for k, v in self.measure_points.items()}
            ms = [m if m.isdigit() else measure_points_map[m] for m in measure_points]
        uri = "/openapi/platform/getPowerStationRealTimeData"
        res = await self.auth.request(uri, {"ps_id_list": ps, "point_id_list": ms, "is_get_point_dict": "1"}, lang=self.lang)
        res = await res.json()
        if "error" in res:
            _LOGGER.error("Error response from %s: %s", uri, res)
            raise PySolarCloudException(res)
        point_dict = dict([(str(point["point_id"]), point) for point in res["result_data"]["point_dict"]])
        plants = {}
        for plant in res["result_data"]["device_point_list"]:
            data = [self._format_measure_point(k[1:], v, point_dict) for k,v in plant.items() if k[0]=='p' and k[1:].isdigit()]
            data_as_dict = {d["code"]: d for d in data}
            plants[str(plant["ps_id"])] = data_as_dict
        _LOGGER.debug("async_get_realtime_data: %s", plants)
        return plants

    async def async_get_historical_data(self, plant_id: str | list[str], start_time: datetime, end_time: datetime = None, *, measure_points=None, interval=timedelta(minutes=60)) -> dict:
        """Return historical data from one or more plants.
        
        plant_id: str | list[str] - The ID of the plant or a list of plant IDs.
        start_time: datetime - The start time of the data to retrieve.
        end_time: datetime - The end time of the data to retrieve. If end_time is not specified, 3 hours of data is returned.
        measure_points: list[str] - A list of measure points to return. If None, all measure points are returned.
        interval: timedelta - The interval in minutes between data points. The minimum interval is 1 minute. Default is 60 minutes.
        Data is returned as a dictionary of lists:
        {
            plant_id: [
                {
                    "timestamp": datetime,
                    "id": str, # Numerical identifier of the measure point
                    "code": str, # Readable code of the measure point (see measure_points dict)
                    "value": float | str,
                    "unit": str,
                    "name": str, # Name of the measure point (in the specified language)
                }
            ]
        }
        """
        if isinstance(plant_id, list):
            ps = str(plant_id)
        else:
            ps = [plant_id]
        if measure_points is None:
            ms = list(self.measure_points.keys())
        else:
            measure_points_map = {v: k for k, v in self.measure_points.items()}
            ms = [m if m.isdigit() else measure_points_map[m] for m in measure_points]
        if end_time is None:
            end_time = start_time + timedelta(hours=3)
        TS_FORMAT = "%Y%m%d%H%M%S"
        uri = "/openapi/platform/getPowerStationPointMinuteDataList"
        params = {
            "ps_id_list": ps, 
            "points": ",".join(["p"+m for m in ms]), 
            "is_get_point_dict": "1",
            "start_time_stamp": start_time.strftime(TS_FORMAT),
            "end_time_stamp": end_time.strftime(TS_FORMAT),
            "minute_interval": str(interval.seconds // 60),
        }
        res = await self.auth.request(uri, params, lang=self.lang)
        res = await res.json()
        if res.get("result_code") != "1":
            _LOGGER.error("Error response from %s: %s", uri, res)
            raise PySolarCloudException(res)
        point_dict = dict([(str(point["point_id"]), point) for point in res["result_data"]["point_dict"]])
        plants = {}
        for plant_id, plant in res["result_data"].items():
            if plant_id == "point_dict":
                continue
            series = []
            for frame in plant:
                data = {}
                ts = datetime.strptime(frame["time_stamp"], TS_FORMAT)
                for k,v in frame.items():
                    if k == "time_stamp":
                        continue
                    else:
                        data = self._format_measure_point(k[1:], v, point_dict)
                        data["timestamp"] = ts
                    series.append(data)
            plants[str(plant_id)] = series
        _LOGGER.debug("async_get_historical_data: %s", plants)
        return plants
    
    def _format_measure_point(self, point_id: str, point_value: str, point_dict: dict) -> dict:
        try:
            v = float(point_value) if point_value is not None else None
        except ValueError:
            v = point_value
        return {
            "id": point_id,
            "code": self.measure_points.get(point_id, point_id),
            "value": v,
            "unit": point_dict.get(point_id, {}).get("point_unit", None),
            "name": point_dict.get(point_id, {}).get("point_name", None),
        }

    measure_points = {
        "83022": "daily_yield", # Wh
        "83024": "total_yield", # Wh
        "83033": "power", # W
        "83019": "power_fraction", # Plant Power/Installed Power of Plant 
        "83006": "meter_daily_yield", # Wh
        "83020": "meter_total_yield", # Wh
        "83011": "meter_e_daily_consumption", # Wh
        "83021": "accumulative_power_consumption_by_meter", # Wh
        "83032": "meter_ac_power", # W
        "83007": "meter_pr", # 
        "83002": "inverter_ac_power", # W
        "83009": "inverter_daily_yield", # Wh
        "83004": "inverter_total_yield", # Wh
        "83012": "p_radiation_h", # W/㎡
        "83013": "daily_irradiation", # Wh/㎡
        "83023": "plant_pr", # 
        "83005": "daily_equivalent_hours", # h
        "83025": "plant_equivalent_hours", # h
        "83018": "daily_yield_theoretical", # Wh
        "83001": "inverter_ac_power_normalization", # W/Wp
        "83008": "daily_equivalent_hours_of_inverter", # h
        "83010": "inverter_pr", # 
        "83016": "plant_ambient_temperature", # ℃
        "83017": "plant_module_temperature", # ℃
        "83046": "pcs_total_active_power", # W
        "83052": "total_load_active_power", # W
        "83067": "total_active_power_of_pv", # W
        "83097": "daily_direct_energy_consumption", # Wh
        "83100": "total_direct_energy_consumption", # Wh
        "83102": "energy_purchased_today", # Wh
        "83105": "total_purchased_energy", # Wh
        "83106": "load_power", # W
        "83118": "daily_load_consumption", # Wh
        "83124": "total_load_consumption", # Wh
        "83119": "daily_feed_in_energy_pv", # Wh
        "83072": "feed_in_energy_today", # Wh
        "83075": "feed_in_energy_total", # Wh
        "83252": "battery_level_soc", # 
        "83129": "battery_soc", # 
        "83232": "total_field_soc", # 
        "83233": "total_field_maximum_rechargeable_power", # W
        "83234": "total_field_maximum_dischargeable_power", # W
        "83235": "total_field_chargeable_energy", # Wh
        "83236": "total_field_dischargeable_energy", # Wh
        "83237": "total_field_energy_storage_maximum_reactive_power", # W
        "83238": "total_field_energy_storage_active_power", # W
        "83239": "total_field_reactive_power", # var
        "83240": "total_field_power_factor", # 
        "83243": "daily_field_charge_capacity", # Wh
        "83241": "total_field_charge_capacity", # Wh
        "83244": "daily_field_discharge_capacity", # Wh
        "83242": "total_field_discharge_capacity", # Wh
        "83548": "total_number_of_charge_discharge", # 
        "83549": "grid_active_power", # W
        "83419": "daily_highest_inverter_power_inverter_installed_capacity", # 
        "83317": "power_forecast", # W
        "83318": "planned_es_charging_discharging_power", # W
        "83319": "planned_es_soc", # 
        "83320": "planned_charging_power", # Wh
        "83321": "planned_discharging_power", # Wh
        "83322": "ess_daily_charge_ems", # Wh
        "83324": "energy_storage_cumulative_charge", # Wh
        "83323": "ess_daily_discharge_ems", # Wh
        "83325": "cumulative_discharge", # Wh
        "83327": "energy_storage_remaining_charge", # Wh
        "83326": "energy_storage_active_power_ems", # W
        "83328": "grid_active_power_ems", # W
        "83329": "pv_active_power_ems", # W
        "83330": "load_active_power_ems", # W
        "83331": "daily_pv_yield_ems", # Wh
        "83332": "total_pv_yield", # Wh
        "83334": "energy_storage_soc_ems", # 
        "83335": "energy_storage_remaining_charge_ems", # Wh
    }