import re

import pytest

from src.patterns.digital import (
    DIGITAL_NAMES,
    DIGITAL_ONLY_MANUFACTURERS,
    DIGITAL_PATTERNS,
    is_digital_camera,
    is_digital_name,
)


def test_digital_patterns_are_compiled():
    for p in DIGITAL_PATTERNS:
        assert isinstance(p, re.Pattern)


def test_digital_names_is_frozenset():
    assert isinstance(DIGITAL_NAMES, frozenset)
    assert len(DIGITAL_NAMES) > 0


def test_digital_only_manufacturers_is_frozenset():
    assert isinstance(DIGITAL_ONLY_MANUFACTURERS, frozenset)
    assert len(DIGITAL_ONLY_MANUFACTURERS) > 0


@pytest.mark.parametrize("name", [
    "PowerShot A520",
    "EOS R5",
    "Cyber-shot DSC-RX100",
    "Lumix GH5",
    "GoPro Hero 10",
    "FinePix S5Pro",
    "CoolPix P1000",
    "OM-D E-M1",
    # Exact digital names
    "Olympus Air",
    "Sigma fp",
    "Leica M10",
])
def test_is_digital_name_true(name):
    assert is_digital_name(name)


@pytest.mark.parametrize("name", [
    "Canon AE-1",
    "Nikon F2",
    "Leica M6",
    "Pentax K1000",
    "Rolleiflex 2.8F",
    "Hasselblad 500C/M",
    "Olympus OM-1",
    "Leica CL",  # 1973 film version
])
def test_is_digital_name_false(name):
    assert not is_digital_name(name)


def test_is_digital_camera_with_manufacturer():
    assert is_digital_camera(name="Random Camera", manufacturer="hp")
    assert is_digital_camera(name="Random Camera", manufacturer="benq")
    assert not is_digital_camera(name="Random Camera", manufacturer="nikon")


def test_is_digital_camera_with_camera_type():
    assert is_digital_camera(name="Generic Camera", camera_type="digital SLR")
    assert not is_digital_camera(name="Generic Camera", camera_type="SLR")
