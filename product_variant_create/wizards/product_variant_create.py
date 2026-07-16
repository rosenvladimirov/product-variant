# Copyright 2023 Rosen Vladimirov, BioPrint Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import groupby

_logger = logging.getLogger(__name__)


def _ids2str(ids):
    return ",".join([str(i) for i in sorted(ids)])


class ProductVariantCreate(models.TransientModel):
    _name = "product.variant.create"
    _inherit = ["image.mixin"]
    _description = "Create Variant from attribute"

    @api.model
    def default_get(self, default_fields):
        result = super().default_get(default_fields)
        if (
            not result.get("product_tmpl_id")
            and self._context.get("active_model") == "product.template"
        ):
            product_tmpl_id = self.env["product.template"].browse(
                self._context["active_id"]
            )
            product_template_attribute_value_ids = self.env[
                "product.template.attribute.value"
            ].search(
                [("product_tmpl_id", "=", product_tmpl_id.id)],
            )
            attribute_ids = []
            for attribute, values in groupby(
                product_template_attribute_value_ids.sorted(
                    lambda r: r.attribute_id.id
                ),
                lambda r: r.attribute_id,
            ):
                # Fix (реш. Росен): зареждай САМО атрибути, които СЪЗДАВАТ вариант
                # (create_variant in always/dynamic). Оригиналът зареждаше всички,
                # вкл. no_variant — те НЕ участват в комбинацията на варианта, значи
                # няма смисъл да се избират тук.
                if attribute.create_variant == "no_variant":
                    continue
                _logger.debug("%s::%s", attribute, list(values))
                attribute_ids.append(
                    Command.create(
                        {
                            "product_tmpl_id": product_tmpl_id.id,
                            "attribute_id": attribute.id,
                        }
                    )
                )
            # Fix: раншата версия създаваше UserError БЕЗ raise (мъртъв guard).
            if not attribute_ids:
                raise UserError(
                    _(
                        "The template has no attributes defined; "
                        "it may be a single product without variants."
                    )
                )
            result.update(
                product_template_attribute_value_ids=attribute_ids,
                product_tmpl_id=product_tmpl_id.id,
            )
        return result

    product_tmpl_id = fields.Many2one("product.template", string="Product Template")
    product_template_attribute_value_ids = fields.One2many(
        comodel_name="product.variant.create.lines",
        inverse_name="product_variant_create_id",
        string="Product attributes",
    )
    combination_indices = fields.Char()
    default_code = fields.Char("Internal Reference")
    barcode = fields.Char(
        "Product barcode",
        help="International Article Number used for product identification.",
    )
    volume = fields.Float("Product volume", digits="Volume")
    weight = fields.Float("Net weight", digits="Stock Weight")

    def _get_template_attribute_values(self):
        """Резолвни избраните (атрибут, стойност) двойки към PTAV на темплейта.
        Ако избраната стойност липсва на съответната attribute line, добави я —
        иначе product.template.attribute.value не съществува и вариантът не може
        да носи стойността."""
        self.ensure_one()
        tmpl = self.product_tmpl_id
        Ptav = self.env["product.template.attribute.value"]
        ptavs = Ptav
        for line in self.product_template_attribute_value_ids:
            attr_line = tmpl.attribute_line_ids.filtered(
                lambda r: r.attribute_id == line.attribute_id
            )
            if not attr_line:
                raise UserError(
                    _("Attribute %s is not defined on the template.")
                    % line.attribute_id.display_name
                )
            if line.product_attribute_value_id not in attr_line.value_ids:
                attr_line.write(
                    {"value_ids": [Command.link(line.product_attribute_value_id.id)]}
                )
            ptav = Ptav.search(
                [
                    ("product_tmpl_id", "=", tmpl.id),
                    ("attribute_id", "=", line.attribute_id.id),
                    (
                        "product_attribute_value_id",
                        "=",
                        line.product_attribute_value_id.id,
                    ),
                ],
                limit=1,
            )
            if ptav:
                ptavs |= ptav
        return ptavs

    def process(self):
        self.ensure_one()
        if not self.product_tmpl_id:
            return False
        tmpl = self.product_tmpl_id
        ptavs = self._get_template_attribute_values()
        if not ptavs:
            raise UserError(_("No attribute values selected; nothing to create."))
        # combination_indices на product.product се смята САМО от variant-affecting
        # PTAV-и (no_variant се изключват) → ползвай _without_no_variant_attributes,
        # иначе guard-ът за „вече съществува" не напасва (стар бъг: сравняваше и
        # product.attribute.value id-та).
        # Вариантът носи само variant-creating PTAV-и (no_variant са опции
        # per-поръчка, не част от варианта); combination_indices на product.product
        # също се смята само от тях.
        variant_ptavs = ptavs._without_no_variant_attributes()
        # Валидирай структурата/конфига на комбинацията, ИГНОРИРАЙКИ no_variant.
        # НЕ ползваме core `_create_product_variant` — то иска ПЪЛНА комбинация вкл.
        # no_variant PTAV (виж docstring-а му) + работи само за dynamic темплейти,
        # затова връщаше празно → „not possible". Тук създаваме варианта директно.
        if not tmpl._is_combination_possible_by_config(
            variant_ptavs, ignore_no_variant=True
        ):
            raise UserError(
                _(
                    "The selected attribute combination is not possible "
                    "for this template."
                )
            )
        self.combination_indices = _ids2str(variant_ptavs.ids)
        # Guard: съществуващ вариант (вкл. архивиран) с тази комбинация.
        existing = (
            self.env["product.product"]
            .with_context(active_test=False)
            .search(
                [
                    ("product_tmpl_id", "=", tmpl.id),
                    ("combination_indices", "=", self.combination_indices),
                ],
                limit=1,
            )
        )
        if existing:
            if existing.active:
                raise UserError(
                    _("This variant already exists: %s") % existing.display_name
                )
            # Архивиран → реактивирай (вместо dangling дубликат).
            existing.sudo().active = True
            variant = existing
        else:
            variant = (
                self.env["product.product"]
                .sudo()
                .create(
                    {
                        "product_tmpl_id": tmpl.id,
                        "product_template_attribute_value_ids": [
                            Command.set(variant_ptavs.ids)
                        ],
                    }
                )
            )
        # Наслои допълнителните полета върху създадения/реактивирания вариант.
        vals = {
            key: value
            for key, value in {
                "default_code": self.default_code,
                "barcode": self.barcode,
                "volume": self.volume,
                "weight": self.weight,
                "image_1920": self.image_1920,
            }.items()
            if value
        }
        if vals:
            variant.sudo().write(vals)
        # Fix: върни action към създадения вариант (старият process не връщаше нищо).
        return {
            "type": "ir.actions.act_window",
            "name": _("Created Variant"),
            "res_model": "product.product",
            "res_id": variant.id,
            "view_mode": "form",
            "target": "current",
        }


class ProductVariantCreateLines(models.TransientModel):
    _name = "product.variant.create.lines"
    _description = "Create Variant from attribute lines"

    product_variant_create_id = fields.Many2one(
        "product.variant.create", string="Product variant create"
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product Template",
    )
    product_attribute_value_id = fields.Many2one(
        "product.attribute.value", string="Attribute Value", required=True
    )
    attribute_id = fields.Many2one("product.attribute", string="Attribute")
