#!/usr/bin/env python3
"""
Utilities for generating HTML or preparing data for HTML templates.
"""
import colorsys
import re


def generate_golden_angle_palette(count=250, start_hex='#d0ffce',
                                  initial_colors=None,
                                  master_list_size=250):
    """Generates a list of visually distinct colors, with an option for a custom start.

    If an `initial_colors` list is provided, it will be used as the
    start of the palette, and seed the rest of the list from the hue
    of the last color in that list.  Otherwise, gnerate a full palette
    starting from `start_hex` using the golden angle (137.5 degrees)
    for hue rotation. Saturation and value are adjusted based on a
    `master_list_size` to ensure colors are always consistent
    regardless of the total count requested.

    Args:
        count (int): The total number of colors to generate.
        start_hex (str): The starting hex color if `initial_colors` is not given.
        initial_colors (list[str], optional): A list of hex colors to start the
                                              palette with. Defaults to None.
        master_list_size (int): The reference size for consistent generation.
    Returns:
        list[str]: A list of color strings in hex format.

    """
    colors_hex = []
    start_index = 0

    if initial_colors:
        # Start with the provided hand-picked colors.
        colors_hex.extend(initial_colors)
        if count <= len(colors_hex):
            return colors_hex[:count]

        # The algorithm will start generating after the initial colors.
        start_index = len(colors_hex)
        # The new starting point is the last of the initial colors.
        start_hex = initial_colors[-1]

    if not start_hex.startswith('#') or len(start_hex) != 7:
        raise ValueError("start_hex must be in #RRGGBB format.")

    # --- 1. Convert the starting hex color to its HSV representation ---
    start_r = int(start_hex[1:3], 16) / 255.0
    start_g = int(start_hex[3:5], 16) / 255.0
    start_b = int(start_hex[5:7], 16) / 255.0
    start_h, start_s, start_v = colorsys.rgb_to_hsv(start_r, start_g, start_b)

    # --- 2. Generate the rest of the palette ---
    golden_angle_increment = 137.5 / 360.0

    # Loop from the start_index to the desired total count.
    for i in range(start_index, count):
        # The hue jump is based on the color's position relative to the start.
        # This ensures the spiral continues correctly from the initial colors.
        hue_jump_index = i - start_index
        hue = (start_h + (hue_jump_index + 1) * golden_angle_increment) % 1.0

        # Vary saturation and value based on the color's absolute index.
        # This maintains consistency across different list lengths.
        saturation = start_s + (i / master_list_size) * 0.1
        value = start_v - (i / master_list_size) * 0.15

        # Ensure saturation and value stay within the valid 0-1 range.
        saturation = max(0, min(1, saturation))
        value = max(0, min(1, value))

        # Convert the new HSV color back to RGB.
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)

        # Convert RGB to a hex string.
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(r * 255), int(g * 255), int(b * 255)
        )
        colors_hex.append(hex_color)

    return colors_hex


def generate_candidate_colors(candidates):
    """
    Generates a dictionary mapping candidate keys to hex color codes.

    :param candidates: A list of candidate keys (e.g., ['C1', 'C2', 'C3']).
    :return: A dictionary like {'C1': '#d0ffce', 'C2': '#cefff9', ...}.
    """
    colors = generate_golden_angle_palette(count=len(candidates) + 5,
                                           initial_colors=[
                                               '#d0ffce', '#cee1ff', '#ffcece', '#ffeab9']
                                           )
    colordict = {}
    for i, cand in enumerate(candidates):
        colordict[cand] = colors[i]
    return colordict


def escape_css_selector(s):
    """
    Escapes a string to be used as a CSS selector, replacing invalid characters with an underscore.
    """
    # This regex finds any character that is not a letter, number, underscore, or hyphen.
    return re.sub(r'[^a-zA-Z0-9_-]', '_', s)
