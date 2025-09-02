#!/usr/bin/env python3
"""Link preview generation for awt.

Provides Open Graph metadata and PNG image generation for social media
link previews (Facebook, Slack, Discord, etc.).
"""

import os
from pathlib import Path
from html import escape
from typing import Optional, Dict, List, Tuple

# Optional dependency - check availability at module level
try:
    import cairosvg  # type: ignore
except ImportError:
    cairosvg = None


# Constants
PREVIEW_WIDTH = 1200
PREVIEW_HEIGHT = 630
VIEWBOX_WIDTH = 317.5
VIEWBOX_HEIGHT = 166.6875
FRAME_FILENAME = 'awt-electorama-linkpreview-frame.svg'


def get_frame_svg_path() -> Path:
    """Get path to the SVG frame file."""
    # Import here to avoid circular imports
    from awt import app, AWT_STATIC

    static_dir = AWT_STATIC or app.static_folder
    return Path(static_dir or 'static') / 'img' / FRAME_FILENAME


def px_to_viewbox(px_value: float) -> float:
    """Convert pixel coordinates to SVG viewBox units."""
    return px_value * (VIEWBOX_WIDTH / PREVIEW_WIDTH)


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text with ellipsis if too long."""
    text = str(text)
    return text if len(text) <= max_length else text[:max_length-1] + '…'


def pick_primary_candidate(candidate_tokens: List[str], canonical_order: List[str],
                          candnames: Dict[str, str]) -> Optional[str]:
    """Choose primary candidate from list using canonical order as tiebreaker."""
    if not candidate_tokens:
        return None

    # Map display names back to tokens if needed
    normalized_tokens = []
    for token in candidate_tokens:
        if token in candnames:
            normalized_tokens.append(token)
        else:
            # Winner string may be a name; try reverse lookup
            reverse_token = next((t for t, n in candnames.items() if n == token), token)
            normalized_tokens.append(reverse_token)

    # Use canonical order for consistent tiebreaking
    order_tokens = list(canonical_order) if canonical_order else sorted(candnames.keys())
    for token in order_tokens:
        if token in normalized_tokens:
            return token

    return normalized_tokens[0] if normalized_tokens else None


def get_candidate_vote_count(token: str, fptp_toppicks: Dict) -> Optional[int]:
    """Extract vote count for candidate from FPTP results."""
    if not token:
        return None

    votes = fptp_toppicks.get(token)
    if isinstance(votes, (int, float)):
        return int(votes)
    if isinstance(votes, list) and votes:
        return int(votes[0]) if isinstance(votes[0], (int, float)) else None
    return None


def compose_preview_svg(identifier: str, max_names: int = 4) -> str:
    """Compose SVG with election results for link preview.

    Args:
        identifier: Election ID
        max_names: Maximum candidates to show

    Returns:
        Complete SVG string with dynamic content injected

    Raises:
        FileNotFoundError: If frame SVG not found
        Various exceptions: For invalid election data
    """
    # Import here to avoid circular imports
    from awt import (build_election_list, get_fileentry_from_election_list,
                     convert_abif_to_jabmod, add_ratings_to_jabmod_votelines)
    from conduits import ResultConduit, get_canonical_candidate_order
    from html_util import generate_candidate_colors

    # Load base frame SVG
    frame_path = get_frame_svg_path()
    if not frame_path.exists():
        raise FileNotFoundError(f"Frame SVG not found: {frame_path}")

    with open(frame_path, 'r', encoding='utf-8') as f:
        base_svg = f.read()

    # Build election model and get results
    election_list = build_election_list()
    fileentry = get_fileentry_from_election_list(identifier, election_list)
    if not fileentry:
        raise ValueError(f"Election not found: {identifier}")

    jabmod = convert_abif_to_jabmod(fileentry['text'], cleanws=True)

    # Get candidate colors and names
    canonical_order = get_canonical_candidate_order(jabmod)
    colordict = generate_candidate_colors(canonical_order)
    candnames = jabmod.get('candidates', {})

    # Calculate results via ResultConduit for consistency
    from conduits import get_complete_resblob_for_linkpreview, get_winners_by_method, get_method_display_info
    resblob = get_complete_resblob_for_linkpreview(jabmod)
    winners_by_method = get_winners_by_method(resblob, jabmod)
    display_info_dict = get_method_display_info(resblob, jabmod)

    # Get FPTP data for vote counts
    fptp_result = resblob.get('FPTP_result', {})
    fptp_toppicks = fptp_result.get('toppicks', {})

    # Pick primary winners using canonical order
    order_tokens = list(canonical_order) if canonical_order else sorted(candnames.keys())

    irv_primary = pick_primary_candidate(winners_by_method.get('IRV', []), order_tokens, candnames)
    cope_primary = pick_primary_candidate(winners_by_method.get('Condorcet', []), order_tokens, candnames)
    fptp_primary = pick_primary_candidate(winners_by_method.get('FPTP', []), order_tokens, candnames)

    # Detect clash: any method disagreement (not just IRV vs Condorcet)
    all_primary_winners = set()
    if irv_primary:
        all_primary_winners.add(irv_primary)
    if cope_primary:
        all_primary_winners.add(cope_primary)
    if fptp_primary:
        all_primary_winners.add(fptp_primary)

    clash = len(all_primary_winners) > 1

    # Get other winners for SVG content
    star_winners = winners_by_method.get('STAR', [])
    star_winner = star_winners[0] if star_winners else None
    approval_winners = winners_by_method.get('Approval', [])

    # Convert STAR token back to name for _build_svg_content compatibility
    star_winner_name = candnames.get(star_winner) if star_winner else None

    # Build dynamic SVG content
    svg_content = _build_svg_content(
        fileentry, jabmod, clash, irv_primary, cope_primary, fptp_primary,
        star_winner_name, approval_winners, colordict, candnames, fptp_toppicks,
        resblob, order_tokens, max_names, display_info_dict
    )

    # Insert content into frame SVG
    if '</svg>' in base_svg:
        return base_svg.replace('</svg>', svg_content + '\n</svg>')
    else:
        return base_svg + svg_content


def _build_svg_content(fileentry: Dict, jabmod: Dict, clash: bool,
                      irv_primary: str, cope_primary: str, fptp_primary: str,
                      star_winner: str, approval_winners: List[str],
                      colordict: Dict, candnames: Dict, fptp_toppicks: Dict,
                      resblob: Dict, order_tokens: List[str], max_names: int,
                      display_info_dict: Dict) -> str:
    """Build the dynamic SVG content string."""
    px = px_to_viewbox

    parts = ['<g id="awt-content" aria-label="awt dynamic content">']

    # Title and stats
    title_text = fileentry.get('title') or jabmod.get('title') or 'Election Results'
    ballots_total = jabmod.get('metadata', {}).get('ballotcount')

    x_left_title = px(80)
    y_title = px(280)
    title_fs = px(30)
    stats_fs = px(24)

    # Title
    parts.append(
        f'<text x="{x_left_title:.3f}" y="{y_title:.3f}" '
        f'style="font-family: DejaVu Sans, Noto Sans, Arial, sans-serif; '
        f'font-size:{title_fs:.3f}px; font-weight:600; fill:#222;">'
        f'{escape(truncate_text(title_text, 64))}</text>'
    )

    # Stats line
    stats_bits = []
    if ballots_total is not None:
        try:
            stats_bits.append(f"Ballots: {int(ballots_total):,}")
        except Exception:
            stats_bits.append(f"Ballots: {ballots_total}")

    if clash:
        stats_bits.append("Different results from different methods")

    if stats_bits:
        parts.append(
            f'<text x="{x_left_title:.3f}" y="{(y_title + px(30)):.3f}" '
            f'style="font-family: DejaVu Sans, Noto Sans, Arial, sans-serif; '
            f'font-size:{stats_fs:.3f}px; fill:#555;">'
            f'{escape(" • ".join(stats_bits))}</text>'
        )

    if clash:
        _add_clash_layout(parts, irv_primary, cope_primary, fptp_primary,
                         star_winner, approval_winners, colordict, candnames,
                         resblob, jabmod, px, display_info_dict)
    else:
        _add_consensus_layout(parts, irv_primary, fptp_primary, order_tokens,
                            colordict, candnames, fptp_toppicks, max_names, px)

    parts.append('</g>')
    return '\n'.join(parts)


def _add_clash_layout(parts: List[str], irv_primary: str, cope_primary: str,
                     fptp_primary: str, star_winner: str, approval_winners: List[str],
                     colordict: Dict, candnames: Dict, resblob: Dict, jabmod: Dict, px,
                     display_info_dict: Dict) -> None:
    """Add clash layout showing multiple method winners."""
    # Map STAR winner name back to token
    def name_to_token(name):
        if not name:
            return None
        for token, cand_name in candnames.items():
            if cand_name == name:
                return token
        return None

    star_primary = name_to_token(star_winner)
    approval_primary = pick_primary_candidate(approval_winners, [], candnames)

    methods = [
        ('IRV', irv_primary),
        ('FPTP', fptp_primary),
        ('Approval', approval_primary),
        ('STAR', star_primary),
        ('Condorcet/Copeland', cope_primary),
    ]

    x_left = px(80)
    y_start = px(340)
    label_fs = px(14)
    box_size = px(26)
    line_fs = px(24)
    block_height = px(50)

    for i, (label, token) in enumerate(methods):
        y_pos = y_start + i * block_height

        # Method label
        parts.append(
            f'<text x="{x_left:.3f}" y="{(y_pos - px(2)):.3f}" '
            f'style="font-family: DejaVu Sans, Noto Sans, Arial, sans-serif; '
            f'font-size:{label_fs:.3f}px; font-weight:600; fill:#333;">'
            f'{escape(label)}</text>'
        )

        # Color box and candidate name
        y_line = y_pos + px(24)
        color = colordict.get(token, '#bbb') if token else '#bbb'
        name = candnames.get(token, token) if token else '—'

        parts.append(
            f'<rect x="{x_left:.3f}" y="{(y_line - box_size*0.8):.3f}" '
            f'width="{box_size:.3f}" height="{box_size:.3f}" '
            f'rx="{(box_size*0.1):.3f}" ry="{(box_size*0.1):.3f}" '
            f'fill="{color}" />'
        )

        votes_info = display_info_dict.get(f'{label}_{token}', '')

        parts.append(
            f'<text x="{(x_left + px(56)):.3f}" y="{y_line:.3f}" '
            f'style="font-family: DejaVu Sans, Noto Sans, Arial, sans-serif; '
            f'font-size:{line_fs:.3f}px; font-weight:700; fill:#111;">'
            f'{escape(str(name))}'
            f'<tspan style="font-size:{(line_fs*0.8):.3f}px; fill:#666;">'
            f'{escape(votes_info)}</tspan></text>'
        )


def _add_consensus_layout(parts: List[str], irv_primary: str, fptp_primary: str,
                         order_tokens: List[str], colordict: Dict, candnames: Dict,
                         fptp_toppicks: Dict, max_names: int, px) -> None:
    """Add consensus layout with big winner and small runners."""
    winner = irv_primary or fptp_primary or (order_tokens[0] if order_tokens else None)
    if not winner:
        return

    x_left = px(80)
    y_winner = px(380)
    big_box = px(56)
    big_fs = px(52)

    # Winner
    parts.append(
        f'<rect x="{x_left:.3f}" y="{(y_winner - big_box*0.8):.3f}" '
        f'width="{big_box:.3f}" height="{big_box:.3f}" '
        f'rx="{(big_box*0.1):.3f}" ry="{(big_box*0.1):.3f}" '
        f'fill="{colordict.get(winner, "#888")}" />'
    )

    winner_name = candnames.get(winner, winner)
    winner_votes = get_candidate_vote_count(winner, fptp_toppicks)
    label = winner_name
    if winner_votes is not None:
        label += f" — {winner_votes:,} top votes"

    parts.append(
        f'<text x="{(x_left + px(72)):.3f}" y="{y_winner:.3f}" '
        f'style="font-family: DejaVu Sans, Noto Sans, Arial, sans-serif; '
        f'font-size:{big_fs:.3f}px; font-weight:800; fill:#111;">'
        f'{escape(label)}</text>'
    )

    # Runners-up
    small_y = y_winner + px(60)
    small_box = px(28)
    small_fs = px(28)

    # Get FPTP ordering for runners
    fptp_order = _get_fptp_candidate_order(fptp_toppicks, order_tokens)
    runners = [c for c in fptp_order if c != winner][:max_names-1]

    for i, token in enumerate(runners):
        y_pos = small_y + i * px(38)
        parts.append(
            f'<rect x="{x_left:.3f}" y="{(y_pos - small_box*0.8):.3f}" '
            f'width="{small_box:.3f}" height="{small_box:.3f}" '
            f'rx="{(small_box*0.1):.3f}" ry="{(small_box*0.1):.3f}" '
            f'fill="{colordict.get(token, "#bbb")}" />'
        )
        parts.append(
            f'<text x="{(x_left + px(56)):.3f}" y="{y_pos:.3f}" '
            f'style="font-family: DejaVu Sans, Noto Sans, Arial, sans-serif; '
            f'font-size:{small_fs:.3f}px; fill:#222;">'
            f'{escape(candnames.get(token, token))}</text>'
        )


def _get_fptp_candidate_order(fptp_toppicks: Dict, fallback_order: List[str]) -> List[str]:
    """Get candidates ordered by FPTP vote count (highest first)."""
    if not fptp_toppicks:
        return fallback_order

    def get_vote_count(item):
        cand, votes = item
        if isinstance(votes, (int, float)):
            return votes
        elif isinstance(votes, list) and len(votes) > 0:
            return votes[0] if isinstance(votes[0], (int, float)) else 0
        return 0

    return [c for c, _ in sorted(fptp_toppicks.items(), key=get_vote_count, reverse=True) if c is not None]



def render_svg_to_png(svg_text: str, width: int = PREVIEW_WIDTH,
                     height: int = PREVIEW_HEIGHT) -> bytes:
    """Render SVG text to PNG bytes.

    Args:
        svg_text: Complete SVG document as string
        width: Output PNG width
        height: Output PNG height

    Returns:
        PNG image as bytes

    Raises:
        RuntimeError: If CairoSVG not available
    """
    if cairosvg is None:
        raise RuntimeError("CairoSVG not available for PNG rendering")

    return cairosvg.svg2png(
        bytestring=svg_text.encode('utf-8'),
        output_width=width,
        output_height=height
    )


def render_svg_file_to_png(svg_path: Path, width: int = PREVIEW_WIDTH,
                           height: int = PREVIEW_HEIGHT) -> bytes:
    """Render an SVG file to PNG bytes using a file URL.

    Using a file URL allows relative hrefs (e.g., embedded images) within
    the SVG to resolve correctly.

    Args:
        svg_path: Path to an SVG file on disk
        width: Output PNG width
        height: Output PNG height

    Returns:
        PNG image as bytes

    Raises:
        RuntimeError: If CairoSVG not available
        FileNotFoundError: If file does not exist
    """
    if cairosvg is None:
        raise RuntimeError("CairoSVG not available for PNG rendering")
    svg_path = Path(svg_path)
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG not found: {svg_path}")
    return cairosvg.svg2png(url=str(svg_path), output_width=width, output_height=height)


def render_svg_file_to_png(svg_path: str, width: int = PREVIEW_WIDTH, height: int = PREVIEW_HEIGHT) -> bytes:
    """Render SVG file to PNG bytes (resolves relative references).

    Args:
        svg_path: Path to SVG file
        width: Output PNG width
        height: Output PNG height

    Returns:
        PNG image as bytes

    Raises:
        RuntimeError: If CairoSVG not available
        FileNotFoundError: If SVG file not found
    """
    if cairosvg is None:
        raise RuntimeError("CairoSVG not available for PNG rendering")

    return cairosvg.svg2png(url=svg_path, output_width=width, output_height=height)


def render_frame_png(width: int = PREVIEW_WIDTH, height: int = PREVIEW_HEIGHT) -> bytes:
    """Render the static frame SVG as PNG.

    Args:
        width: Output PNG width
        height: Output PNG height

    Returns:
        PNG image as bytes

    Raises:
        RuntimeError: If CairoSVG not available
        FileNotFoundError: If frame SVG not found
    """
    if cairosvg is None:
        raise RuntimeError("CairoSVG not available for PNG rendering")

    frame_path = get_frame_svg_path()
    if not frame_path.exists():
        raise FileNotFoundError(f"Frame SVG not found: {frame_path}")

    return cairosvg.svg2png(url=str(frame_path), output_width=width, output_height=height)


def render_generic_preview_png() -> bytes:
    """Render the generic preview image as PNG.

    Returns:
        PNG image as bytes

    Raises:
        RuntimeError: If CairoSVG not available
        FileNotFoundError: If generic SVG not found
    """
    if cairosvg is None:
        raise RuntimeError("CairoSVG not available for PNG rendering")

    # Import here to avoid circular imports
    from awt import app, AWT_STATIC

    static_dir = AWT_STATIC or app.static_folder or 'static'
    generic_svg_path = Path(static_dir) / 'img' / 'awt-generic-linkpreview.svg'

    if not generic_svg_path.exists():
        raise FileNotFoundError(f"Generic SVG not found: {generic_svg_path}")

    return cairosvg.svg2png(url=str(generic_svg_path))


def get_election_preview_metadata(identifier: str) -> Dict[str, str]:
    """Get Open Graph metadata for an election.

    Args:
        identifier: Election ID

    Returns:
        Dict with og_title, og_description, og_image keys

    Raises:
        ValueError: If election not found
    """
    # Import here to avoid circular imports
    from awt import build_election_list, get_fileentry_from_election_list, convert_abif_to_jabmod
    from conduits import ResultConduit
    from html_util import get_method_ordering

    election_list = build_election_list()
    fileentry = get_fileentry_from_election_list(identifier, election_list)
    if not fileentry:
        raise ValueError(f"Election not found: {identifier}")

    jabmod = convert_abif_to_jabmod(fileentry['text'], cleanws=True)
    candnames = jabmod.get('candidates', {})

    # Use conduits.py to get all results (same pattern as awt.py election pages)
    from conduits import get_complete_resblob_for_linkpreview, get_winners_by_method
    resblob = get_complete_resblob_for_linkpreview(jabmod)
    winners_by_method = get_winners_by_method(resblob, jabmod)

    title_plain = fileentry.get('title') or identifier

    # Build description using standardized winner data
    summary_parts = []

    for method, winner_tokens in winners_by_method.items():
        if winner_tokens:
            winner_names = [candnames.get(tok, tok) for tok in winner_tokens]
            summary_parts.append(f"{method}: {', '.join(winner_names)}")

    if summary_parts:
        # Check if all winners are the same
        all_winner_sets = []
        for method, winner_tokens in winners_by_method.items():
            if winner_tokens:
                all_winner_sets.append(set(winner_tokens))

        if len(all_winner_sets) > 1 and len(set().union(*all_winner_sets)) == 1:
            # All methods have same single winner
            first_winner = list(all_winner_sets[0])[0]
            winner_name = candnames.get(first_winner, first_winner)
            description = f"All abiflib voting methods agree on the winner: {winner_name}"
        else:
            description = f"abiflib voting methods show different winners ({'; '.join(summary_parts)})"
    else:
        description = f"Compare FPTP, IRV, Condorcet, STAR, and Approval."

    # Truncate long descriptions
    if len(description) > 240:
        description = description[:237] + "..."

    return {
        'og_title': f"{title_plain} — Results (awt)",
        'og_description': description,
        'og_image': f"/preview-img/id/{identifier}.png"
    }
