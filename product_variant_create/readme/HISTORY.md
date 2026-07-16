## 19.0.1.0.0 (2026-07-16)

- Migration to 19.0.
- Fix: the wizard now loads only variant-creating attributes
  (`create_variant` in `always`/`dynamic`). The original loaded every
  attribute of the template, including `no_variant` ones, which do not take
  part in the variant combination and should not be offered here.
- Fix: the "template has no attributes" guard now actually raises
  `UserError` (previously the exception was built but never raised, so the
  wizard opened empty on a variant-less template).
- Fix: the "variant already exists" check now builds the combination key from
  `product.template.attribute.value` ids (matching
  `product.product.combination_indices`) instead of `product.attribute.value`
  ids, so the guard actually matches existing variants.
- Variant creation is done directly (`product.product.create`) using only the
  variant-creating PTAVs. The combination is validated with
  `_is_combination_possible_by_config(..., ignore_no_variant=True)`, and an
  archived matching variant is reactivated instead of leaving a duplicate.
  (Core `_create_product_variant` is intentionally not used: it requires the
  full combination *including* `no_variant` attributes, which this wizard does
  not collect, so it rejected valid combinations with "not possible".)
- The wizard now returns an action opening the created variant.
- Housekeeping: renamed `wizards/product_variant_create.py.xml` to `.xml`,
  fixed the source-file header to the AGPL/OCA notice, and removed the dead
  `combination_indices` onchange (invisible field).

## 16.0.1.0.0

This module follows the conception of the product configurator in the part of
creating a new variant.
