"""Per-rail lumped efficiency, eta=Pout/Pin (S9, TI SLVA390A Eq.13)."""

from .._validation import keys, number


class ConverterModel:
    def __init__(self, config):
        keys(
            config,
            {"propulsion_efficiency", "payload_efficiency", "hotel_efficiency"},
            "converters",
        )
        self.propulsion = number(
            config.get("propulsion_efficiency", 1),
            "propulsion_efficiency",
            positive=True,
            maximum=1,
        )
        self.payload = number(
            config.get("payload_efficiency", 1), "payload_efficiency", positive=True, maximum=1
        )
        self.hotel = number(
            config.get("hotel_efficiency", 1), "hotel_efficiency", positive=True, maximum=1
        )

    def input_power(self, propulsion_W, payload_W, hotel_W):
        return propulsion_W / self.propulsion + payload_W / self.payload + hotel_W / self.hotel
