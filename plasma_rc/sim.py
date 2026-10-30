"""Compatibility imports; new callers import the relevant optional adapter directly."""
from .simulation.spice import V_B, V_E, V_OP, I_OP, PART, bulb, spice, tran, thev, pulse
from .simulation.firmware import TICK, STEPS, RUN_TICKS, firmware_sim, firmware_tools_present
