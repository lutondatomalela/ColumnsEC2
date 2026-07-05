# -*- coding: utf-8 -*-
from columns_ec2.core.materials import parse_concrete_strength, concrete_props
from columns_ec2.core.utils import safe_float


def test_safe_float_decimal_comma():
    assert safe_float("1,25") == 1.25


def test_concrete_class_parser():
    assert parse_concrete_strength("C40/50") == 40.0
    assert concrete_props(30.0)["fctm"] > 0
