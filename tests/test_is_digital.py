import pytest

from src.patterns.digital import is_digital_camera


@pytest.mark.parametrize("name,camera_type,manufacturer", [
    # Pattern matches
    ("PowerShot A520", "", ""),
    ("EOS R5", "", ""),
    ("EOS 5D Mark IV", "", ""),
    ("Cyber-shot DSC-RX100", "", ""),
    ("Lumix GH5", "", ""),
    ("GoPro Hero 10", "", ""),
    ("iPhone 14 Pro", "", ""),
    ("Nikon Z6", "", ""),
    ("FinePix S5Pro", "", ""),
    ("CoolPix P1000", "", ""),
    ("OM-D E-M1", "", ""),
    ("GFX 50S", "", ""),
    ("D-Lux 7", "", ""),
    ("EasyShare C300", "", ""),
    # Exact digital names
    ("Olympus Air", "", ""),
    ("Sigma fp", "", ""),
    ("Leica M10", "", ""),
    ("Epson R-D1", "", ""),
    # Digital-only manufacturers
    ("Some Camera", "", "hp"),
    ("Some Camera", "", "hewlett packard"),
    ("Some Camera", "", "benq"),
    ("Some Camera", "", "om system"),
    ("Some Camera", "", "dell"),
    # Camera type containing digital keyword
    ("Generic Camera", "DSLR", ""),
    ("Generic Camera", "digital compact", ""),
])
def test_is_digital_true(name, camera_type, manufacturer):
    assert is_digital_camera(name=name, camera_type=camera_type, manufacturer=manufacturer)


@pytest.mark.parametrize("name,camera_type,manufacturer", [
    # Classic film cameras
    ("Nikon F2", "", "nikon"),
    ("Canon AE-1", "", "canon"),
    ("Leica M6", "", "leica"),
    ("Pentax K1000", "", "pentax"),
    ("Olympus OM-1", "", "olympus"),
    ("Minolta SRT 101", "", "minolta"),
    ("Yashica-Mat 124G", "", "yashica"),
    ("Contax T2", "", "contax"),
    ("Rolleiflex 2.8F", "", "rollei"),
    ("Hasselblad 500C/M", "", "hasselblad"),
    ("Mamiya RB67", "", "mamiya"),
    # 1973 film Leica CL (NOT the digital one)
    ("Leica CL", "", "leica"),
    # Polaroid/Instant film cameras
    ("Polaroid SX-70", "", "polaroid"),
    # Medium format
    ("Bronica SQ-A", "", "bronica"),
])
def test_is_digital_false(name, camera_type, manufacturer):
    assert not is_digital_camera(name=name, camera_type=camera_type, manufacturer=manufacturer)
