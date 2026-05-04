from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol
from .const import DOMAIN, CONF_GEMINI_KEY, CONF_OCR_SPACE_KEY

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
            data_schema=vol.Schema({
                vol.Optional(CONF_GEMINI_KEY): str,
                vol.Optional(CONF_OCR_SPACE_KEY, default="[REDACTED]"): str,
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ShoppingListOptionsFlow(config_entry)


class ShoppingListOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for the component."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # We must update the data in the entry
            new_data = dict(self.config_entry.data)
            new_data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_GEMINI_KEY, 
                    default=data.get(CONF_GEMINI_KEY, "")
                ): str,
                vol.Optional(
                    CONF_OCR_SPACE_KEY, 
                    default=data.get(CONF_OCR_SPACE_KEY, "[REDACTED]")
                ): str,
            })
        )
