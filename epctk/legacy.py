from epctk.elements.sap_types import OpeningType, Opening, HeatLossElement, HeatLossElementTypes


def convert_old_style_openings(dwelling):
    # This gives behaviour consistent with the old way of doing
    # things, BUT it means that the door is treated as glazed for the
    # solar gain calc!
    opening_type = OpeningType(gvalue=dwelling.gvalue,
                               frame_factor=dwelling.frame_factor,
                               light_transmittance=dwelling.light_transmittance,
                               roof_window=False)
    dwelling.openings = [
        Opening(dwelling.Aglazing_front, dwelling.orientation,
                opening_type),
        Opening(dwelling.Aglazing_back, dwelling.orientation + 180,
                opening_type),
        Opening(dwelling.Aglazing_left, dwelling.orientation - 90,
                opening_type),
        Opening(dwelling.Aglazing_right, dwelling.orientation + 90,
                opening_type),
    ]


def convert_old_style_heat_loss(dwelling):
    # Again, check treatment of glazing vs external door
    Aglazing_actual = max(0., dwelling.Aglazing - dwelling.Aextdoors)
    Aextdoor_actual = dwelling.Aglazing - Aglazing_actual
    assert Aglazing_actual >= 0
    assert Aextdoor_actual >= 0

    dwelling.heat_loss_elements = [
        HeatLossElement(Aglazing_actual, dwelling.Uglazing,
                        HeatLossElementTypes.GLAZING, True),
        HeatLossElement(Aextdoor_actual, dwelling.Uextdoor,
                        HeatLossElementTypes.OPAQUE_DOOR, True),
        HeatLossElement(dwelling.Aroof, dwelling.Uroof,
                        HeatLossElementTypes.EXTERNAL_ROOF, True),
        HeatLossElement(dwelling.Aextwall, dwelling.Uextwall,
                        HeatLossElementTypes.EXTERNAL_WALL, True),
        HeatLossElement(dwelling.Agndfloor, dwelling.Ugndfloor,
                        HeatLossElementTypes.EXTERNAL_FLOOR, True),
        HeatLossElement(dwelling.Apartywall, dwelling.Uparty_wall,
                        HeatLossElementTypes.PARTY_WALL, False),
        HeatLossElement(dwelling.Abasementfloor, dwelling.Ubasementfloor,
                        HeatLossElementTypes.EXTERNAL_FLOOR, True),
        HeatLossElement(dwelling.Abasementwall, dwelling.Ubasementwall,
                        HeatLossElementTypes.EXTERNAL_WALL, True),
    ]
    if dwelling.get('Aexposedfloor') is not None:
        dwelling.heat_loss_elements.append(
            HeatLossElement(dwelling.Aexposedfloor, dwelling.Uexposedfloor, HeatLossElementTypes.EXTERNAL_FLOOR, True))

    if dwelling.get('Aroominroof') is not None:
        dwelling.heat_loss_elements.append(
            HeatLossElement(dwelling.Aroominroof, dwelling.Uroominroof, HeatLossElementTypes.EXTERNAL_ROOF, True))


def convert_old_style_geometry(dwelling):
    if not dwelling.get('openings'):
        convert_old_style_openings(dwelling)
    if not dwelling.get('heat_loss_elements'):
        convert_old_style_heat_loss(dwelling)