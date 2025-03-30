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
