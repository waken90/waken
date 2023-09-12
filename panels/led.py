import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from math import pi
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.preview = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.preview.connect("draw", self.on_draw)
        data_misc = screen.apiclient.send_request("server/database/item?namespace=mainsail&key=miscellaneous.entries")
        if data_misc:
            self._printer.add_led_presets(data_misc['result']['value'][next(iter(data_misc["result"]["value"]))])
        self.color_data = [0, 0, 0, 0]
        self.color_order = 'RGBW'
        self.presets = {
            "on": [1.0, 1.0, 1.0, 1.0],
            "off": [0.0, 0.0, 0.0, 0.0]
        }
        self.scales = {}
        self.buttons = []
        self.leds = self._printer.get_leds()
        self.current_led = self.leds[0] if len(self.leds) == 1 else None
        self.open_selector(None, self.current_led)

    def color_available(self, idx):
        return (
            (idx == 0 and 'R' in self.color_order)
            or (idx == 1 and 'G' in self.color_order)
            or (idx == 2 and 'B' in self.color_order)
            or (idx == 3 and 'W' in self.color_order)
        )

    def activate(self):
        if self.current_led is not None:
            self.set_title(f"{self.current_led}")

    def set_title(self, title):
        self._screen.base_panel.set_title(self.prettify(title))

    def back(self):
        if len(self.leds) > 1:
            self.set_title(self._screen.panels[self._screen._cur_panels[-1]].title)
            self.open_selector(led=None)
            return True
        return False

    def open_selector(self, widget=None, led=None):
        for child in self.content.get_children():
            self.content.remove(child)
        if led is None:
            self.content.add(self.led_selector())
        else:
            self.content.add(self.color_selector(led))
        self.content.show_all()

    def led_selector(self):
        self.current_led = None
        columns = 3 if self._screen.vertical_mode else 4
        grid = self._gtk.HomogeneousGrid()
        for i, led in enumerate(self.leds):
            name = led.split()[1] if len(led.split()) > 1 else led
            button = self._gtk.Button(None, name.upper(), style=f"color{(i % 4) + 1}")
            button.connect("clicked", self.open_selector, led)
            grid.attach(button, (i % columns), int(i / columns), 1, 1)
        scroll = self._gtk.ScrolledWindow()
        scroll.add(grid)
        return scroll

    def color_selector(self, led):
        logging.info(led)
        self.current_led = led
        self.set_title(f"{self.current_led}")
        grid = self._gtk.HomogeneousGrid()
        self.color_data = self._printer.get_led_color(led)
        self.color_order = self._printer.get_led_color_order(led)
        if self.color_data is None or self.color_order is None:
            self.back()
            return
        presets_data = self._printer.get_led_presets(led)
        if presets_data:
            self.presets.update(self.parse_presets(presets_data))
        scale_grid = self._gtk.HomogeneousGrid()
        colors = "RGBW"
        for idx, col_value in enumerate(self.color_data):
            if not self.color_available(idx):
                continue
            button = self._gtk.Button(label=f'{colors[idx].upper()}', style=f"color{idx + 1}")
            color = [0, 0, 0, 0]
            color[idx] = 1
            button.connect("clicked", self.apply_preset, color)
            button.set_hexpand(False)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=255, step=1)
            scale.set_value(round(col_value * 255))
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            scale.connect("button-release-event", self.apply_scales)
            scale.connect("value_changed", self.update_preview)
            self.scales[idx] = scale
            scale_grid.attach(button, 1, idx, 1, 1)
            scale_grid.attach(scale, 2, idx, 3, 1)
        grid.attach(scale_grid, 0, 0, 2, 1)

        preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        preview_box.get_style_context().add_class("frame-item")
        preview_box.add(Gtk.Label(label=_("Color")))
        preview_box.add(self.preview)
        preset_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        preset_list.add(preview_box)
        for i, key in enumerate(self.presets):
            button = self._gtk.Button(None, key.upper(), style=f"color{(i % 4) + 1}")
            button.connect("clicked", self.apply_preset, self.presets[key])
            preset_list.add(button)
        self.preview.queue_draw()
        scroll = self._gtk.ScrolledWindow()
        scroll.add(preset_list)
        grid.attach(scroll, 2, 0, 1, 1)
        return grid

    def on_draw(self, da, ctx):
        ctx.set_source_rgb(self.color_data[0], self.color_data[1], self.color_data[2])
        w = da.get_allocated_width()
        h = da.get_allocated_height()
        r = min(w, h) / 2
        ctx.translate(w / 2, h / 2)
        ctx.arc(0, 0, r, 0, 2 * pi)
        ctx.fill()

    def update_preview(self, args):
        self.update_color_data()
        self.preview.queue_draw()

    def process_update(self, action, data):
        if action != 'notify_status_update':
            return
        if self.current_led in data and "color_data" in data[self.current_led]:
            self.update_scales(data[self.current_led]["color_data"][0])
            self.preview.queue_draw()

    def update_scales(self, color_data):
        for idx in self.scales:
            self.scales[idx].set_value(int(color_data[idx] * 255))
            self.color_data[idx] = color_data[idx]

    def update_color_data(self):
        for idx in self.scales:
            self.color_data[idx] = round(self.scales[idx].get_value() / 255, 4)

    def apply_preset(self, widget, color_data):
        self.update_scales(color_data)
        self.apply_scales()

    def apply_scales(self, *args):
        self.update_color_data()
        self.set_led_color(self.color_data)

    def set_led_color(self, color_data):
        name = self.current_led.split()[1] if len(self.current_led.split()) > 1 else self.current_led
        self._screen._send_action(None, "printer.gcode.script",
                                  {"script": KlippyGcodes.set_led_color(name, color_data)})

    @staticmethod
    def parse_presets(presets_data) -> {}:
        parsed = {}
        for preset in presets_data.values():
            name = preset["name"].lower()
            parsed[name] = [
                round(preset[color] / 255, 4)
                for color in ["red", "green", "blue", "white"]
                if color in preset and preset[color] is not None
            ]
        return parsed
