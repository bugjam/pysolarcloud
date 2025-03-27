"""A Python library to interact with Sungrow's iSolarCloud API."""

from abc import ABC, abstractmethod
from enum import StrEnum
import logging
import time
from urllib.parse import quote_plus

from aiohttp import ClientResponse, ClientSession

_LOGGER = logging.getLogger(__name__)

class Server(StrEnum):
    """Enum of iSolarCloud servers."""
    China = "https://gateway.isolarcloud.com"
    International = "https://gateway.isolarcloud.com.hk"
    Europe = "https://gateway.isolarcloud.eu"
    Australia = "https://augateway.isolarcloud.com"

class AbstractAuth(ABC):
    """Abstract class to make authenticated requests.
    
    Subclasses must implement the async_get_access_token method
    and may call async_fetch_tokens and async_refresh_tokens.
    """

    def __init__(self, websession: ClientSession, server: Server | str, client_id: str, client_secret: str, app_id: str):
        """Initialize the authorization session."""
        self.websession = websession
        self.host = server.value if isinstance(server, Server) else server
        self.appkey = client_id
        self.access_key = client_secret
        self.app_id = app_id

    def auth_url(self, redirect_uri: str) -> str:
        """Return the URL to authorize the user."""
        match self.host:
            case Server.China.value:
                auth_server = "web3.isolarcloud.com"
                cloud_id = 1
            case Server.International.value:
                auth_server = "web3.isolarcloud.com.hk"
                cloud_id = 2
            case Server.Europe.value:
                auth_server = "web3.isolarcloud.eu"
                cloud_id = 3
            case Server.Australia.value:
                auth_server = "auweb3.isolarcloud.com"
                cloud_id = 7
        return f"https://{auth_server}/#/authorized-app?cloudId={cloud_id}&applicationId={self.app_id}&redirectUrl={quote_plus(redirect_uri)}"

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""

    async def request(self, path, data, *, lang="_en_US", **kwargs) -> ClientResponse:
        """Make a request to iSolarCloud.
        
        Parameters:
        path -- the path to request
        data -- the data to send
        lang -- the language to use (default "_en_US", supported languages are "_en_US", "_zh_CN", "_ja_JP", "_es_ES", "_de_DE", "_pt_BR", "_fr_FR", "_it_IT", "_ko_KR", "_nl_NL", "_pl_PL", "_vi_VN", "_zh_TW"
        **kwargs -- additional arguments to pass to the request
        """
        if not path.startswith("/"):
            path = f"/{path}"
        if headers := kwargs.pop("headers", {}):
            headers = dict(headers)
        access_token = await self.async_get_access_token()
        headers = {**headers, "x-access-key": self.access_key, "Authorization": f"Bearer {access_token}"}
        body = {**data, "appkey": self.appkey, "lang": lang}
        return await self.websession.request(
            "post", f"{self.host}{path}", json=body, **kwargs, headers=headers,
        )
    
    async def async_fetch_tokens(self, code, redirect_uri, **kwargs) -> ClientResponse:
        """Fetch the access and refresh tokens."""
        if headers := kwargs.pop("headers", {}):
            headers = dict(headers)
        headers = {**headers, "x-access-key": self.access_key, "Content-type": "application/json"}
        body = {
            "appkey": self.appkey, 
            "code": code, 
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }
        response = await self.websession.request("post", f"{self.host}/openapi/apiManage/token", json=body, headers=headers, **kwargs)
        return await response.json()

    async def async_refresh_tokens(self, refresh_token, **kwargs) -> ClientResponse:
        """Refresh the access token."""
        if headers := kwargs.pop("headers", {}):
            headers = dict(headers)
        headers = {**headers, "x-access-key": self.access_key}
        body = {
            "appkey": self.appkey, 
            "refresh_token": refresh_token
        }
        response = await self.websession.request("post", f"{self.host}/openapi/apiManage/refreshToken", json=body, **kwargs, headers=headers)
        return await response.json()
    
class Auth(AbstractAuth):
    """Class to authenticate with the SolarCloud API."""

    def __init__(self, host: str, appkey: str, access_key: str, app_id: str, *, websession: ClientSession = None):
        """Initialize the auth."""
        if websession is None:
            websession = ClientSession(raise_for_status=True)
        super().__init__(websession, host, appkey, access_key, app_id)
        self.tokens = None

    async def async_authorize(self, code, redirect_uri):
        """Authorize the user."""
        ts = await self.async_fetch_tokens(code, redirect_uri)
        print(ts)
        if "access_token" not in ts:
            _LOGGER.error("Authorization failed: %s", str(ts))
            return
        self.tokens = {
            "access_token": ts["access_token"],
            "refresh_token": ts["refresh_token"],
            "expires_at": int(time.time()) + ts["expires_in"] - 20,
        }
        _LOGGER.debug("Authorization succesful")

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if self.tokens is None:
            raise PySolarCloudException({"error": "auth_not_initialised", "error_description": "You must authorize first."})
        if self.tokens["expires_at"] < int(time.time()):
            ts = await self.async_refresh_tokens(self.tokens["refresh_token"])
            self.tokens = {
                "access_token": ts["access_token"],
                "refresh_token": ts["refresh_token"],
                "expires_at": int(time.time()) + ts["expires_in"] - 20,
            }
        return self.tokens["access_token"]

class PySolarCloudException(Exception):
    """Exception class raised by PySolarCloud when communication with the iSolarCloud service fails."""
    def __init__(self, err: dict):
        super().__init__(err["error"])
        self.error = err["error"]
        self.error_description = err["error_description"]
        self.req_serial_num = err.get("req_serial_num", None)