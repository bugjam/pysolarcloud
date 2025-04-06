import asyncio
from datetime import datetime
from . import AbstractAuth, PySolarCloudException, _LOGGER

class Control:
    """Class to interact with the Grid Control API."""
    def __init__(self, auth: AbstractAuth, *, lang: str = "_en_US"):
        """Initialize the control API."""
        self.auth = auth

    async def async_param_config_verification(self, device_uuid: str, set_type: int) -> bool:
        """Verifies whether the device supports parameter configuration."""
        uri = "/openapi/platform/paramSettingCheck"
        res = await self.auth.request(uri, {"set_type": set_type, "uuid": str(device_uuid)})
        res.raise_for_status()
        data = await res.json()
        _LOGGER.debug("async_param_config_verification: %s", data)
        if data.get("result_code") == "1" and data["result_data"]["check_result"] == "1":
            supported = data["result_data"]["dev_result_list"][0]["check_result"]
            if supported == "1":
                return True
            elif supported == "0":
                return False
        raise PySolarCloudException(f"Could not check support for device {device_uuid} set_type {set_type}: {data}")

    async def async_check_read_support(self, device_uuid: str) -> bool:    
        """Check if the device supports read operations."""
        return await self.async_param_config_verification(device_uuid, 2)

    async def async_check_update_support(self, device_uuid: str) -> bool:    
        """Check if the device supports read operations."""
        return await self.async_param_config_verification(device_uuid, 0)

    async def wait_for_task(self, device_uuid: str, task_id: str) -> dict:
        """Poll for the task to be completed."""
        uri = "/openapi/platform/getParamSettingTask"
        params = {
            "task_id": str(task_id),
            "uuid": str(device_uuid),
        }
        await asyncio.sleep(2)
        while True:
            res = await self.auth.request(uri, params)
            res.raise_for_status()
            data = await res.json()
            _LOGGER.debug("wait_for_task: %s", data)
            if data.get("result_code") == "1" and data["result_data"]["command_status"] == 2:
                # Task is still running
                await asyncio.sleep(5)
                continue
            elif data.get("result_code") == "1" and data["result_data"]["command_status"] == 8:
                return data["result_data"]["param_list"]
            else:
                _LOGGER.error("Task not successful %s: %s", task_id, data)
                raise PySolarCloudException(f"Task not succesful {task_id}: {data}")

    async def async_read_parameters(self, device_uuid: str, param_list : list[str]|None = None) -> dict:
        """Read the parameters from the device."""
        uri = "/openapi/platform/paramSetting"
        if param_list is None:
            ps = self.config_parameters.keys()
        else:
            param_map = {v: k for k, v in self.config_parameters.items()}
            ps = [param_map.get(p,p) for p in param_list]
        _LOGGER.debug("async_read_parameters: param_list=%s", ps)
        plist = [ { "param_code": p, "set_value": "" } for p in ps ]
        params = {
            "set_type": 2,
            "uuid": str(device_uuid),
            "task_name": f"Readback {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "expire_second": 120,
            "param_list": plist,
        }
        res = await self.auth.request(uri, params)
        res.raise_for_status()
        data = await res.json()
        _LOGGER.debug("async_read_parameters: %s", data)
        if data.get("result_code") == "1" and data["result_data"]["check_result"] == "1" \
                and data["result_data"]["dev_result_list"][0]["code"] == "1":
            task_id = data["result_data"]["dev_result_list"][0]["task_id"]
            results = await self.wait_for_task(device_uuid, task_id)
            return [self._format_param_readout(param, param["return_value"]) for param in results]
        raise PySolarCloudException(f"Could not read parameters from device {device_uuid}: {data}")

    async def async_update_parameters(self, device_uuid: str, param_values : dict) -> dict:
        """Update parameters to the device."""
        uri = "/openapi/platform/paramSetting"
        param_codes = {v: k for k, v in self.config_parameters.items()}
        plist = [ { "param_code": param_codes.get(str(p),str(p)), "set_value": str(v) } for p,v in param_values ]
        _LOGGER.debug("async_update_parameters: param_valuest=%s", plist)
        params = {
            "set_type": 0,
            "uuid": str(device_uuid),
            "task_name": f"Update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "expire_second": 120,
            "param_list": plist,
        }
        res = await self.auth.request(uri, params)
        res.raise_for_status()
        data = await res.json()
        _LOGGER.debug("async_update_parameters: %s", data)
        if data.get("result_code") == "1" and data["result_data"]["check_result"] == "1" \
                and data["result_data"]["dev_result_list"][0]["code"] == "1":
            task_id = data["result_data"]["dev_result_list"][0]["task_id"]
            results = await self.wait_for_task(device_uuid, task_id)
            return [self._format_param_readout(param, param["set_value"]) for param in results]
        raise PySolarCloudException(f"Could not update parameters of device {device_uuid}: {data}")

    def _format_param_readout(self, param: str, value: str) -> dict:
        """Format the parameter response."""
        readout = {
            "id": param["param_code"],
            "code": self.config_parameters.get(param["param_code"], param["param_code"]),
            "name": param["point_name"],
            "value": value,
            "unit": param.get("unit", ""),
            "precision": param.get("set_precision", None),
        }
        if param.get("set_val_name"):
            value_set_names = param["set_val_name"].split("|")
            value_set_values = param["set_val_name_val"].split("|")
            if value in value_set_values:
                readout["value"] = value_set_names[value_set_values.index(value)]
                readout["value_set"] = dict(zip(value_set_names, value_set_values))
        else:
            try:
                readout["value"] = float(value)
            except ValueError:
                pass
        return readout

    config_parameters = {
        "10001": "soc_upper_limit",
        "10002": "soc_lower_limit",
        "10004": "charge_discharge_command",
        "10005": "charge_discharge_power",
        "10007": "limited_power_switch",
        "10008": "active_power_limit_ratio",
        "10009": "reactive_power_regulation_mode",
        "10010": "q_t",
        "10011": "power_on",
        "10012": "feed_in_limitation",
        "10013": "feed_in_limitation_value",
        "10014": "feed_in_limitation_ratio",
        "10017": "external_ems_heartbeat",
        "10024": "battery_first",
        "10025": "active_power_soft_start_after_fault",
        "10026": "active_power_soft_start_time_after_fault",
        "10027": "active_power_soft_start",
        "10028": "active_power_soft_start_gradient",
        "10029": "active_power_gradient_control",
        "10030": "active_power_decline_gradient",
        "10031": "active_power_rising_gradient",
        "10032": "active_power_setting_persistence",
        "10033": "shutdown_when_active_power_limit_to_0",
        "10034": "reactive_response",
        "10035": "reactive_power_regulation_time",
        "10036": "pf",
        "10065": "forced_charging",
        "10066": "forced_charging_valid_time",
        "10067": "forced_charging_start_time_1_hour",
        "10068": "forced_charging_start_time_1_minute",
        "10069": "forced_charging_end_time_1_hour",
        "10070": "forced_charging_end_time_1_minute",
        "10071": "forced_charging_target_soc_1",
        "10072": "forced_charging_start_time_2_hour",
        "10073": "forced_charging_start_time_2_minute",
        "10074": "forced_charging_end_time_2_hour",
        "10075": "forced_charging_end_time_2_minute",
        "10076": "forced_charging_target_soc_2",
        "10091": "max_charging_power",
        "10092": "max_discharging_power",

        # These are defined in API documentation but are rejected by the API as duplicates of 10071 and 10076
        # "10015": "forced_charging_target_soc1",
        # "10016": "forced_charging_target_soc2",

        # These are defined in API documentation but cause validation error from the API
        # "10003": "energy_management_mode",
        # "10006": "existing_inverter",
        # "10082": "charge_discharge_command_in_external_dispatch_mode",
        # "10083": "charging_discharging_power_in_external_dispatch_mode",
        # "10084": "power_limiting_command_in_external_dispatch_mode",
        # "10085": "ems_heartbeat_settings_in_external_dispatch_mode",
        # "10086": "energy_management_mode",
        # "10087": "feed_in_limitation_ratio_in_external_dispatch_mode",
        # "10088": "feed_in_limitation_on_off_in_external_dispatch_mode",
        # "10089": "feed_in_limitation_value_in_external_dispatch_mode",
    }
