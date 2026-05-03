from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN

class ShoppingListConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shopping List OCR."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Nákupník", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({})
        )
