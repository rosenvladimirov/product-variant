# Copyright 2016-2018 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import odoo.addons.decimal_precision as dp
from odoo import api, models, fields


class SaleManageVariantWebsite(models.TransientModel):
    _name = 'sale.manage.variant.website'

    product_tmpl_id = fields.Many2one(
        comodel_name='product.template', string="Template", required=True)
    product_tmpl_html = fields.Html('Products variants', compute="_get_products_variants")
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=True,
                                   help="Pricelist for current sales order.")

    def _get_html(self):
        result = {}
        context = dict(self.env.context)
        rcontext = {
                    'pricelist': self.pricelist_id,
                    'product': self.product_tmpl_id,
                    'get_attribute_value_ids': self.get_attribute_value_ids,
                    }
        result['html'] = self.env.ref(
            'sale_order_variant_mgmt_website.product').with_context(context).render(
                rcontext)
        return result

    @api.multi
    def _get_products_variants(self):
        for rec in self:
            if rec.product_tmpl_id:
                rec.product_tmpl_html = rec._get_html()['html']


    def get_attribute_value_ids(self, product):
        """ list of selectable attributes of a product
        :return: list of product variant description
           (variant id, [visible attribute ids], variant price, variant sale price)
        """
        # product attributes with at least two choices
        quantity = product._context.get('quantity') or 1
        product = product.with_context(quantity=quantity)

        visible_attrs_ids = product.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 1).mapped('attribute_id').ids
        to_currency = self.pricelist_id.currency_id
        attribute_value_ids = []
        for variant in product.product_variant_ids:
            if to_currency != product.currency_id:
                price = variant.currency_id.compute(variant.website_public_price, to_currency) / quantity
            else:
                price = variant.website_public_price / quantity
            visible_attribute_ids = [v.id for v in variant.attribute_value_ids if v.attribute_id.id in visible_attrs_ids]
            attribute_value_ids.append([variant.id, visible_attribute_ids, variant.website_price / quantity, price])
        return attribute_value_ids

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        if self.product_tmpl_id:
            self.product_tmpl_html = rec._get_html()['html']

    @api.multi
    def button_transfer_to_order(self):
        context = self.env.context
        record = self.env[context['active_model']].browse(context['active_id'])
        if context['active_model'] == 'sale.order.line':
            sale_order = record.order_id
        else:
            sale_order = record
        OrderLine = self.env['sale.order.line']
        lines2unlink = OrderLine
        for line in self.variant_line_ids:
            product = self._get_product_variant(line.value_x, line.value_y)
            order_line = sale_order.order_line.filtered(
                lambda x: x.product_id == product
            )
            if order_line:
                if not line.product_uom_qty:
                    # Done this way because there's a side effect removing here
                    lines2unlink |= order_line
                else:
                    order_line.product_uom_qty = line.product_uom_qty
            elif line.product_uom_qty:
                vals = OrderLine.default_get(OrderLine._fields.keys())
                vals.update({
                    'product_id': product.id,
                    'product_set_id': self.product_set_id,
                    'product_uom': product.uom_id,
                    'product_uom_qty': line.product_uom_qty,
                    'order_id': sale_order.id,
                })
                order_line = OrderLine.new(vals)
                order_line.product_id_change()
                order_line_vals = order_line._convert_to_write(
                    order_line._cache)
                sale_order.order_line.browse().create(order_line_vals)
        lines2unlink.unlink()

