"""One node drawn on the editor canvas.

A node stores the *key* of the field it exposes, never its translated label:
the label is looked up on every redraw, so switching language re-labels nodes
that are already on the canvas and presets saved in one language open correctly
in the other.
"""

from __future__ import annotations

from ...core import fields
from ...i18n import t
from ...theme import COLOR_ARGUMENT, COLOR_FOLDER, COLOR_LIANT, MUTED, SURFACE, SURFACE2, TEXT

class Node:
    """Visual graph node used by the node editor canvas."""

    NW, NH = 200, 90
    PORT_R = 7

    def __init__(self, canvas, node_id, node_family, type_key, x, y, label_override=None):
        self.canvas      = canvas
        self.id          = node_id
        self.node_family = node_family   # "argument" | "liant" | "folder"
        self.type_key    = type_key      # clé NODE_TYPES pour "argument", None sinon
        self.x, self.y   = x, y
        if node_family == "argument":
            self._label = label_override or (fields.label(type_key) if type_key else "Argument")
            self._label_is_default = not bool(label_override)
        elif node_family == "liant":
            self._label = label_override or "-"
            self._label_is_default = False
        else:
            default_folder = t("node_default_folder")
            self._label = label_override if label_override else default_folder
            self._label_is_default = not bool(label_override)
        self.separator  = ""
        self.canvas_ids = []
        self._selected  = False
        self.draw()

    @property
    def color(self):
        if self.node_family == "folder":  return COLOR_FOLDER
        if self.node_family == "liant":   return COLOR_LIANT
        return fields.color(self.type_key)

    @property
    def label(self): return self._label

    @label.setter
    def label(self, v):
        self._label = v
        self.draw()

    @property
    def display_label(self):
        """The label to show, resolved in the active locale."""
        if self.node_family == "folder":
            return (t("node_default_folder")
                    if getattr(self, "_label_is_default", False) else self._label)
        if self.node_family == "argument" and self.type_key in fields.FIELDS:
            return fields.label(self.type_key)
        return self._label

    @property
    def field(self):
        if self.node_family == "argument":
            return fields.resolver_of(self.type_key)
        return None

    # Redrawing the full node keeps rendering logic simple and avoids tracking many incremental canvas updates.
    def draw(self):
        for cid in self.canvas_ids:
            self.canvas.delete(cid)
        self.canvas_ids.clear()
        x, y, w, h = self.x, self.y, self.NW, self.NH
        c        = self.color
        bw       = 3 if self._selected else 2
        out      = TEXT if self._selected else c
        sel_fill = "#252320" if self._selected else SURFACE2

        shadow  = self.canvas.create_rectangle(x+4, y+4, x+w+4, y+h+4,
                      fill="#0d0c0b", outline="", tags=f"node_{self.id}")
        body    = self.canvas.create_rectangle(x, y, x+w, y+h,
                      fill=sel_fill, outline=out, width=bw, tags=f"node_{self.id}")
        header  = self.canvas.create_rectangle(x+bw, y+bw, x+w-bw, y+25,
                      fill=c, outline="", tags=f"node_{self.id}")

        if self.node_family == "folder":
            icon = "📁"; badge = t("node_badge_folder"); bcol = COLOR_FOLDER
        elif self.node_family == "liant":
            icon = "🔗"; badge = t("node_badge_liant");  bcol = COLOR_LIANT
        else:
            icon = "📌"; badge = t("node_badge_arg");    bcol = COLOR_ARGUMENT
        display_label = self.display_label
        title = self.canvas.create_text(x + w//2, y + 14,
                    text=f"{icon}  {display_label}",
                    fill="#0f1a1c", font=("Segoe UI", 8, "bold"),
                    tags=f"node_{self.id}")

        if self.node_family == "folder":
            sub_text  = t("node_dbl_rename")
            hint_text = t("node_parent_hint")
        elif self.node_family == "liant":
            sub_text  = t("node_fixed_val", v=self._label)
            hint_text = t("node_dbl_edit")
        else:
            sep_disp  = f'"{self.separator}"' if self.separator else t("node_sep_none")
            sub_text  = t("node_field", f=fields.resolver_of(self.type_key))
            hint_text = t("node_sep", s=sep_disp)

        sub_t  = self.canvas.create_text(x + w//2, y + 48,
                     text=sub_text, fill=MUTED, font=("Segoe UI", 7),
                     tags=f"node_{self.id}")
        hint_t = self.canvas.create_text(x + w//2, y + 63,
                     text=hint_text, fill=c, font=("Segoe UI", 6, "bold"),
                     tags=f"node_{self.id}")
        del_b  = self.canvas.create_text(x + w - 10, y + 14,
                     text="✕", fill="#0f1a1c", font=("Segoe UI", 8, "bold"),
                     tags=(f"node_{self.id}", f"del_{self.id}"))
        badge_t = self.canvas.create_text(x + 8, y + h - 10,
                     text=badge, fill=bcol,
                     font=("Segoe UI", 6, "bold"), anchor="w",
                     tags=f"node_{self.id}")

        port_in  = self.canvas.create_oval(
            x - self.PORT_R, y + h//2 - self.PORT_R,
            x + self.PORT_R, y + h//2 + self.PORT_R,
            fill=SURFACE, outline=c, width=2,
            tags=(f"node_{self.id}", f"port_in_{self.id}"))
        port_out = self.canvas.create_oval(
            x + w - self.PORT_R, y + h//2 - self.PORT_R,
            x + w + self.PORT_R, y + h//2 + self.PORT_R,
            fill=c, outline=c,
            tags=(f"node_{self.id}", f"port_out_{self.id}"))

        self.canvas_ids = [cid for cid in
            [shadow, body, header, title, sub_t, hint_t, del_b, badge_t, port_in, port_out]
            if cid is not None]

        if self.node_family == "folder":
            port_name_in = self.canvas.create_polygon(
                x + w//2 - 8, y + h,
                x + w//2 + 8, y + h,
                x + w//2,     y + h + 13,
                fill=SURFACE2, outline=COLOR_LIANT, width=2,
                tags=(f"node_{self.id}", f"port_name_in_{self.id}"))
            lbl_nom = self.canvas.create_text(x + w//2, y + h + 22,
                text=t("node_nom"), fill=COLOR_LIANT, font=("Segoe UI", 6, "bold"),
                tags=f"node_{self.id}")
            self.canvas_ids += [port_name_in, lbl_nom]

    def set_selected(self, sel):
        self._selected = sel
        self.draw()

    def port_in_pos(self):      return (self.x,           self.y + self.NH // 2)
    def port_out_pos(self):     return (self.x + self.NW, self.y + self.NH // 2)
    def port_name_in_pos(self): return (self.x + self.NW // 2, self.y + self.NH + 13)

    def move(self, dx, dy):
        self.x += dx; self.y += dy
        for cid in self.canvas_ids:
            self.canvas.move(cid, dx, dy)

    # Hit testing includes the additional folder-name port area exposed by folder nodes.
    def hit_test(self, mx, my):
        extra = 25 if self.node_family == "folder" else 0
        return self.x <= mx <= self.x + self.NW and self.y <= my <= self.y + self.NH + extra

    def hit_delete(self, mx, my):
        dx, dy = self.x + self.NW - 10, self.y + 14
        return abs(mx - dx) < 10 and abs(my - dy) < 10

    def hit_port_out(self, mx, my):
        px, py = self.port_out_pos()
        return abs(mx - px) < 14 and abs(my - py) < 14

    def hit_port_in(self, mx, my):
        px, py = self.port_in_pos()
        return abs(mx - px) < 14 and abs(my - py) < 14

    def hit_port_name_in(self, mx, my):
        if self.node_family != "folder": return False
        px, py = self.port_name_in_pos()
        return abs(mx - px) < 16 and abs(my - py) < 16
