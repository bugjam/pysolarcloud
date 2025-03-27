# pysolarcloud

A Python package to interact with the [iSolarCloud API](https://developer-api.isolarcloud.com/) by Sungrow.

The current version has only very basic functionality:
* OAuth2 authentication
* Getting a list plants
* Getting details of a plant
* Getting "real-time" data of a plant (Data is updated every 5 minutes according to Sungrow's documentation)
* Getting historical data

## Quirks
The iSolarCloud API is quite new and not very mature. Some tips:
* The authorisation flow is based on OAuth2 but doesn't work exactly as you would expect
* The `state` parameter is not passed back after to the authorisation step. This makes it more tricky to resume the flow in a client application.
* User is asked to approve the authorisation if the flow is invoked again, e.g. in case the tokens have expired - unlike many OAuth2 implementations who will perform a "silent" authorisation if the user has already approved the access.
* The API documentation lists a lot of data points which do not seem to be returned from my inverter, it probably varies between models.
* There are different iSolarCloud servers for different regions, see the `pysolarcloud.Server` enum
* API endpoints accept a language code but respond with Chinese text when when English is requested

# Usage

## Installation

```
pip install pysolarcloud
```

## Register your app
1. Create an account in the [iSolarCloud Developer Portal](https://developer-api.isolarcloud.com/)
2. Create an app in the developer portal
   * Answer "Yes" to authorize with OAuth2.0
   * Enter a Redirect URL for your app (this can be changed later)
3. Wait for approval by Sungrow
4. Find the needed configuration details in the developer portal. You will need:
   * Appkey
   * Secret Key
   * Application Id (This is shown as a query parameter within the Authorize URL in the developer portal)

## Example

```python
from pysolarcloud import Auth, Server
from pysolarcloud.plants import Plants

app_key = "your app key"
secret_key = "your secret key"
app_id = "your app id"
redirect_uri = "your redirect uri"

auth = Auth(Server.Europe, app_key, secret_key, app_id)
url = Auth.auth_url(redirect_uri)
```
1. Redirect user to `url`
2. User selects plant(s) and grants authorisation
3. iSolarCloud will redirect the user to `redirect_uri` with query parameter `code`
```python
await auth.async_authorize(code, redirect_uri)
plants_api = Plants(auth)
plant_list = await plants_api.async_get_plants()
```

The `Auth` class keeps the access between calls and refreshes it when needed. If you prefer to manage this state yourself, you can create your own subclass of `AbstractAuth`.

# Contributions
Ideas or contributions are welcome. I am not afiliated with Sungrow, I'm just another user of the API. My main use case will be a HomeAssistant integration based on this package.

I don't currently have a need for the Grid Control APIs and I might not be able to test them on my own plant[^1] - but let me know if you are interested.

[^1]: because it's controlled by [Heartbeat](https://1komma5.com/en/offer/energymanager-heartbeat/)

Enjoy!
