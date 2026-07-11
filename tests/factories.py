"""Declarative factories for the sample payloads used across the test suite.

The TOON parser and renderer operate on plain Python data (dicts, lists and
scalars), so the structured payloads are built with ``factory_boy``'s
``DictFactory``. Each factory declares the shape of one kind of record and,
when called, returns an ordinary ``dict`` with real nested ``dict``/``list``
values -- which is precisely what the DRF parser/renderer consume.

Scalar and collection samples that don't map onto a structured record are
listed explicitly in ``SAMPLE_PAYLOADS`` so every case a human needs to reason
about is visible in one place.
"""

from __future__ import annotations

from dataclasses import dataclass

import factory


class UserFactory(factory.DictFactory):
    """A user record: integer id, string name and a boolean flag."""

    id = 1
    name = "alice"
    active = True


class ItemFactory(factory.DictFactory):
    """A line item: string sku and integer quantity."""

    sku = "abc"
    qty = 2


class ComplexDocumentFactory(factory.DictFactory):
    """A deeply nested document mixing objects, lists, floats and null."""

    user = factory.SubFactory(UserFactory, id=99, name="bob", active=False)
    tags = factory.List(["x", "y", "z"])
    scores = factory.List([1.5, 2.5, 3.5])
    metadata = None
    items = factory.List(
        [
            factory.SubFactory(ItemFactory, sku="abc", qty=2),
            factory.SubFactory(ItemFactory, sku="def", qty=5),
        ]
    )


@dataclass(frozen=True)
class Payload:
    """A single named sample payload used to parametrize the tests."""

    id: str
    value: object


# One representative value per data type the parser/renderer must handle.
# Kept as an explicit list so a developer can read every case top to bottom.
SAMPLE_PAYLOADS: list[Payload] = [
    # Scalars.
    Payload("string", "hello world"),
    Payload("empty_string", ""),
    Payload("unicode_string", "héllo — 世界 🌍"),
    Payload("integer", 42),
    Payload("negative_integer", -7),
    Payload("zero", 0),
    Payload("float", 3.14),
    Payload("bool_true", True),
    Payload("bool_false", False),
    Payload("none", None),
    # Collections of scalars.
    Payload("empty_list", []),
    Payload("list_of_ints", [1, 2, 3]),
    Payload("list_of_strings", ["a", "b", "c"]),
    Payload("mixed_list", [1, "two", 3.0, True, None]),
    # Mappings built from the declarative factories above.
    Payload("empty_dict", {}),
    Payload("flat_dict", UserFactory()),
    Payload("nested_dict", {"outer": {"inner": {"value": [1, {"deep": "d"}]}}}),
    Payload(
        "list_of_dicts",
        [
            UserFactory(id=1, name="a", active=True),
            UserFactory(id=2, name="b", active=False),
        ],
    ),
    Payload("complex_document", ComplexDocumentFactory()),
]
