from abiflib import (
    convert_abif_to_jabmod,
    htmltable_pairwise_and_winlosstie,
    get_Copeland_winners,
    html_score_and_star,
    ABIFVotelineException,
    full_copecount_from_abifmodel,
    copecount_diagram,
    IRV_dict_from_jabmod,
    get_IRV_report,
    FPTP_result_from_abifmodel,
    get_FPTP_report,
    pairwise_count_dict,
    STAR_result_from_abifmodel,
    scaled_scores
)
from abiflib.irv_tally import IRV_result_from_abifmodel, IRV_dict_from_jabmod
from abiflib.pairwise_tally import pairwise_result_from_abifmodel
from abiflib.approval_tally import (
    approval_result_from_abifmodel,
    get_approval_report
)
from html_util import generate_candidate_colors

from dataclasses import dataclass, field
from typing import Dict, Any


def get_canonical_candidate_order(jabmod):
    """
    Get consistent candidate ordering based on FPTP vote totals.

    Args:
        jabmod: The ABIF model

    Returns:
        list: Candidates ordered by FPTP vote count (highest first),
              falling back to alphabetical if FPTP unavailable
    """
    # Compute FPTP to get vote-based ordering
    from abiflib.fptp_tally import FPTP_result_from_abifmodel

    try:
        fptp_result = FPTP_result_from_abifmodel(jabmod)
        fptp_toppicks = fptp_result.get('toppicks', {})

        if fptp_toppicks:
            def get_vote_count(item):
                cand, votes = item
                if isinstance(votes, (int, float)):
                    return votes
                elif isinstance(votes, list) and len(votes) > 0:
                    return votes[0] if isinstance(votes[0], (int, float)) else 0
                else:
                    return 0

            fptp_ordered_candidates = sorted(
                fptp_toppicks.items(), key=get_vote_count, reverse=True)
            return [cand for cand, votes in fptp_ordered_candidates if cand is not None]
    except Exception:
        pass

    # Fallback to alphabetical ordering
    if jabmod and 'candidates' in jabmod:
        return sorted(jabmod['candidates'].keys())
    else:
        return []


@dataclass
class ResultConduit:
    jabmod: Dict[str, Any] = field(default_factory=dict)
    resblob: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.jabmod:
            raise TypeError(
                "Please pass in jabmod= param on ResultsConduit init")
        self.resblob = {}

    def _extract_notices(self, method_tag: str, result_dict: dict) -> None:
        """Extract notices from voting method result using consistent tag-based naming"""
        if 'notices' not in self.resblob:
            self.resblob['notices'] = {}
        self.resblob['notices'][method_tag] = result_dict.get('notices', [])

    def _add_irv_tie_notices(self, irv_dict: dict) -> dict:
        """Add notices for IRV tiebreaker situations"""
        result = irv_dict.copy()
        # Preserve any notices provided by abiflib and append tie notices
        existing = irv_dict.get('notices', []) or []
        result['notices'] = list(existing)

        # Check if election had ties
        if not irv_dict.get('has_tie', False):
            return result

        # Look for rounds with random elimination
        roundmeta = irv_dict.get('roundmeta', [])
        tie_rounds = []

        for round_data in roundmeta:
            if round_data.get('random_elim', False):
                tie_info = {
                    'round_num': round_data.get('roundnum', 0),
                    'tied_candidates': round_data.get('tiecandlist', []),
                    'eliminated': round_data.get('eliminated', []),
                    'vote_count': round_data.get('bottom_votes_percand', 0)
                }
                tie_rounds.append(tie_info)

        # Generate notices for each tie
        for tie in tie_rounds:
            if len(tie['tied_candidates']) >= 2:
                tied_names = []
                eliminated_names = []

                # Get candidate display names
                canddict = irv_dict.get('canddict', {})
                for cand_token in tie['tied_candidates']:
                    display_name = canddict.get(cand_token, cand_token)
                    tied_names.append(display_name)

                for cand_token in tie['eliminated']:
                    if cand_token in tie['tied_candidates']:
                        display_name = canddict.get(cand_token, cand_token)
                        eliminated_names.append(display_name)

                # Create notice
                tied_list = " and ".join(tied_names)

                # Handle case where no one was eliminated (final round tie)
                if eliminated_names:
                    eliminated_list = " and ".join(eliminated_names)
                    notice_text = f"In Round {tie['round_num']}, {tied_list} were tied with exactly {tie['vote_count']} votes each for fewest votes. IRV rules require eliminating the candidate(s) with fewest votes. This result used simulated random selection, eliminating {eliminated_list}. In a real election, this would be resolved by lot drawing or other official tiebreaker procedure."
                else:
                    # Final round tie - no elimination, both win
                    notice_text = f"In Round {tie['round_num']}, {tied_list} were tied with exactly {tie['vote_count']} votes each in the final round. Since this is a tie for the most votes in the final round, both candidates are declared IRV winners. In a real election, this might be resolved by lot drawing or other official tiebreaker procedure depending on jurisdiction."

                notice = {
                    "notice_type": "warning",
                    "short": f"Round {tie['round_num']} tiebreaker used",
                    "long": notice_text
                }
                result['notices'].append(notice)

        return result

    def _add_star_tie_notices(self, star_result: dict) -> dict:
        """Add notices for STAR tie situations"""
        result = star_result.copy()
        if 'notices' not in result:
            result['notices'] = []

        # Check if STAR result is a tie
        winner_str = star_result.get('winner', '') or ''
        if "tie " in winner_str:
            # Extract candidate names from the tie string
            tied_candidates = []
            # Look for candidates mentioned in the winner string
            if star_result.get('scores'):
                for cand_token, cand_data in star_result['scores'].items():
                    cand_name = cand_data.get('candname', '')
                    if cand_name and cand_name in winner_str:
                        tied_candidates.append(cand_name)

            if len(tied_candidates) >= 2:
                tied_list = " and ".join(tied_candidates)

                # Get runoff information
                fin1_votes = star_result.get('fin1votes', 0)
                fin2_votes = star_result.get('fin2votes', 0)
                total_voters = star_result.get('totalvoters', 0)

                notice = {
                    "notice_type": "warning",
                    "short": "STAR runoff ended in tie",
                    "long": f"In the STAR runoff, {tied_list} were tied with exactly {fin1_votes} votes each out of {total_voters} total voters. This represents a perfect tie in the automatic runoff between the top two scoring candidates. In a real election, this might be resolved by lot drawing or other official tiebreaker procedure depending on jurisdiction."
                }
                result['notices'].append(notice)

        return result

    def _add_pairwise_tie_notices(self, pairwise_result: dict) -> dict:
        """Add notices for pairwise/Condorcet tie situations"""
        result = pairwise_result.copy()
        if 'notices' not in result:
            result['notices'] = []

        # Check for Copeland ties - use self.resblob data that's already been set
        if hasattr(self, 'resblob') and self.resblob.get('is_copeland_tie', False):
            copewinners = self.resblob.get('copewinners', [])

            if len(copewinners) >= 2:
                # Get candidate display names from resblob context
                tied_names = []
                for token in copewinners:
                    # Use the copewinnerstring which has display names
                    pass

                # Use the existing copewinnerstring instead of trying to reconstruct
                copewinnerstring = self.resblob.get('copewinnerstring', '')

                notice = {
                    "notice_type": "note",
                    "short": "No Condorcet winner found",
                    "long": f"This election has no Condorcet winner. {copewinnerstring} are tied for the most pairwise victories (Copeland tie). Each of these candidates beats the same number of opponents in head-to-head comparisons, creating a cycle in the tournament. The Copeland/pairwise table below shows the detailed win-loss-tie records that result in this tie."
                }
                result['notices'].append(notice)

        return result

    def update_FPTP_result(self, jabmod) -> "ResultConduit":
        """Add FPTP result to resblob"""
        fptp_result = FPTP_result_from_abifmodel(jabmod)
        self.resblob['FPTP_result'] = fptp_result
        self._extract_notices('fptp', fptp_result)
        # self.resblob['FPTP_text'] = get_FPTP_report(jabmod)
        return self

    def update_IRV_result(self, jabmod, include_irv_extra=False, transform_ballots=True) -> "ResultConduit":
        """Add IRV result to resblob, delegating transforms/notices to abiflib."""

        # Backwards compatibility with abiflib v0.32.0
        try:
            # TODO: rename to "IRV_result"
            # Build IRV result (handles optional transform + notices)
            irv_result = IRV_result_from_abifmodel(jabmod, transform_ballots=transform_ballots, include_irv_extra=include_irv_extra)
            self.resblob['IRV_result'] = irv_result
            self.resblob['IRV_dict'] = irv_result['irv_dict']
        except TypeError as e:
            import datetime
            print(f" ------------ [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] "
                  f"Upgrade abiflib to v0.32.1 or later for IRVextra support.")
            self.resblob['IRV_dict'] = IRV_dict_from_jabmod(jabmod)
            self.resblob['IRV_result'] = IRV_result_from_abifmodel(jabmod, transform_ballots=transform_ballots)

        # Convert sets to lists for JSON serialization in templates
        irv_dict = self.resblob['IRV_dict']
        if 'roundmeta' in irv_dict:
            for round_meta in irv_dict['roundmeta']:
                if 'hypothetical_transfers' in round_meta:
                    round_meta['next_choices'] = round_meta.pop(
                        'hypothetical_transfers')
                for key in ['eliminated', 'all_eliminated', 'bottomtie']:
                    if key in round_meta and isinstance(round_meta[key], set):
                        round_meta[key] = list(round_meta[key])

        self.resblob['IRV_text'] = get_IRV_report(self.resblob['IRV_dict'])

        # Append tiebreaker notices if needed (preserving any from abiflib)
        irv_with_tie_notices = self._add_irv_tie_notices(self.resblob['IRV_dict'])
        self._extract_notices('irv', irv_with_tie_notices)
        return self

    def update_pairwise_result(self, jabmod, transform_ballots: bool = False) -> "ResultConduit":
        # Get pairwise result with notices first
        pairwise_result = pairwise_result_from_abifmodel(jabmod, transform_ballots=transform_ballots)
        pairwise_matrix = pairwise_result['pairwise_matrix']

        # Use the same pairwise matrix for copecount to ensure consistency
        copecount = full_copecount_from_abifmodel(jabmod, pairdict=pairwise_matrix)
        copewinners = get_Copeland_winners(copecount)
        cwstring = ", ".join(copewinners)
        self.resblob['copewinners'] = copewinners
        self.resblob['copewinnerstring'] = cwstring
        self.resblob['is_copeland_tie'] = len(copewinners) > 1
        self.resblob['dotsvg_html'] = copecount_diagram(
            copecount, outformat='svg')
        self.resblob['pairwise_dict'] = pairwise_matrix

        # Extract notices from original pairwise result (for cycles/ties)
        self._extract_notices('pairwise', pairwise_result)

        # Pairwise tie notice now generated by abiflib (pairwise_tally)
        self.resblob['pairwise_html'] = htmltable_pairwise_and_winlosstie(jabmod,
                                                                          snippet=True,
                                                                          validate=True,
                                                                          modlimit=2500)
        if jabmod and 'candidates' in jabmod:
            # Use canonical FPTP-based candidate ordering for consistent colors
            canonical_order = get_canonical_candidate_order(jabmod)
            self.resblob['colordict'] = generate_candidate_colors(canonical_order)
        else:
            self.resblob['colordict'] = {}

        # --- Precompute no-preference counts and percentages (minimal AWT-side plan)
        try:
            total_ballots = int(jabmod.get('metadata', {}).get('ballotcount', 0) or 0)
        except Exception:
            total_ballots = 0
        self.resblob['total_ballots'] = total_ballots

        # Build paircells: per matchup counts and percentages (denominator = total_ballots)
        candtoks = list(pairwise_matrix.keys())
        paircells = {}
        for rk in candtoks:
            paircells[rk] = {}
            for ck in candtoks:
                if rk == ck:
                    paircells[rk][ck] = None
                    continue
                ck_score = int((pairwise_matrix.get(ck, {}) or {}).get(rk, 0) or 0)
                rk_score = int((pairwise_matrix.get(rk, {}) or {}).get(ck, 0) or 0)
                if total_ballots > 0:
                    no_pref = max(total_ballots - (ck_score + rk_score), 0)
                    ck_pct = (ck_score / total_ballots) * 100.0
                    rk_pct = (rk_score / total_ballots) * 100.0
                    no_pref_pct = (no_pref / total_ballots) * 100.0
                else:
                    no_pref = 0
                    ck_pct = rk_pct = no_pref_pct = 0.0
                paircells[rk][ck] = {
                    'ck_score': ck_score,
                    'rk_score': rk_score,
                    'no_pref': no_pref,
                    'ck_pct': ck_pct,
                    'rk_pct': rk_pct,
                    'no_pref_pct': no_pref_pct,
                }
        self.resblob['paircells'] = paircells
        return self

    def update_STAR_result(self, jabmod, colordict=None) -> "ResultConduit":
        scorestar = {}
        self.resblob['STAR_html'] = html_score_and_star(jabmod)
        scoremodel = STAR_result_from_abifmodel(jabmod)
        scorestar['scoremodel'] = scoremodel
        stardict = scaled_scores(jabmod, target_scale=50)
        from awt import add_html_hints_to_stardict
        scorestar['starscale'] = \
            add_html_hints_to_stardict(
                scorestar['scoremodel'], stardict, colordict)

        # Generate STAR tie notices if needed
        star_result_with_notices = self._add_star_tie_notices(scoremodel)
        # Extract notices using consistent method
        self._extract_notices('star', star_result_with_notices)

        # Keep backward compatibility for now
        star_notices = scoremodel.get('notices', [])
        if star_notices:
            scorestar['star_foot'] = \
                'NOTE: Since ratings or stars are not present in the provided ballots, ' + \
                'allocated stars are estimated using a Borda-like formula.'

        self.resblob['scorestardict'] = scorestar
        return self

    def update_approval_result(self, jabmod) -> "ResultConduit":
        """Add approval voting result to resblob"""
        approval_result = approval_result_from_abifmodel(jabmod)
        self.resblob['approval_result'] = approval_result
        self.resblob['approval_text'] = get_approval_report(jabmod)
        # Extract notices using consistent method
        self._extract_notices('approval', approval_result)
        # Keep backward compatibility
        self.resblob['approval_notices'] = approval_result.get('notices', [])
        return self

    def update_all(self, jabmod):
        '''Call all of the update methods for updating resconduit blob'''
        # This is example code to replace the old _get_jabmod_to_resblob
        resconduit = ResultConduit(jabmod=jabmod)
        resconduit = resconduit.update_FPTP_result(jabmod)
        resconduit = resconduit.update_IRV_result(jabmod)
        resconduit = resconduit.update_pairwise_result(jabmod)
        resconduit = resconduit.update_STAR_result(jabmod)
        resconduit = resconduit.update_approval_result(jabmod)
        return self


def get_winners_by_method(resblob, jabmod=None):
    """Extract winners from each voting method in a standardized format.

    Args:
        resblob: Complete ResultConduit resblob with all method results
        jabmod: Original jabmod (for candidate name lookup if needed)

    Returns:
        dict: Method names mapped to list of winner tokens
        Example: {'FPTP': ['BrandenRobinson'], 'IRV': ['MartinMichlmayr'], 'Condorcet': ['MartinMichlmayr']}
    """
    winners = {}

    # FPTP winners
    fptp_result = resblob.get('FPTP_result', {})
    if fptp_result.get('winners'):
        winners['FPTP'] = fptp_result['winners']

    # IRV winners
    irv_dict = resblob.get('IRV_dict', {})
    if irv_dict.get('winner'):
        winners['IRV'] = irv_dict['winner']

    # Condorcet/Copeland winners
    if resblob.get('copewinners'):
        winners['Condorcet'] = resblob['copewinners']

    # STAR winners
    star_model = resblob.get('scorestardict', {}).get('scoremodel', {})
    star_winner_tokens = star_model.get('winner_tokens')
    if star_winner_tokens:
        winners['STAR'] = star_winner_tokens

    # Approval winners
    approval_result = resblob.get('approval_result', {})
    if approval_result.get('winners'):
        winners['Approval'] = approval_result['winners']

    return winners


def has_method_clash(resblob, jabmod=None):
    """Determine if voting methods disagree on winners.

    Args:
        resblob: Complete ResultConduit resblob with all method results
        jabmod: Original jabmod (for candidate name lookup if needed)

    Returns:
        bool: True if methods disagree, False if consensus
    """
    winners_by_method = get_winners_by_method(resblob, jabmod)

    # Get primary winner from each method (first winner if multiple)
    primary_winners = set()

    for method, winners in winners_by_method.items():
        if winners:
            # For ties/cycles, pick first winner alphabetically for comparison
            if isinstance(winners, list) and winners:
                primary_winners.add(winners[0])
            elif isinstance(winners, str):
                primary_winners.add(winners)

    # Clash if more than one distinct primary winner
    return len(primary_winners) > 1


def get_method_display_info(resblob, jabmod=None):
    """Get display-ready vote information for each method's winners.

    Args:
        resblob: Complete ResultConduit resblob with all method results
        jabmod: Original jabmod (for candidate name lookup if needed)

    Returns:
        dict: Method-candidate pairs mapped to display info strings
        Example: {'FPTP_BdaleGarbee': ' — 227 first-place votes (47.8%)',
                 'STAR_BdaleGarbee': ' — 291 final-round votes (61.3%)'}
    """
    display_info = {}
    candnames = jabmod.get('candidates', {}) if jabmod else {}

    # FPTP display info
    fptp_result = resblob.get('FPTP_result', {})
    fptp_toppicks = fptp_result.get('toppicks', {})
    total_votes = fptp_result.get('total_votes_recounted', 0)

    # Determine ballot type for FPTP terminology
    ballot_type = None
    if 'approval_result' in resblob:
        ballot_type = resblob['approval_result'].get('ballot_type')

    for token, votes in fptp_toppicks.items():
        if isinstance(votes, (int, float)) and total_votes > 0:
            percentage = (votes / total_votes) * 100
            vote_type = "first-place votes" if ballot_type == "ranked" else "votes"
            display_info[f'FPTP_{token}'] = f" — {int(votes):,} {vote_type} ({percentage:.1f}%)"
        elif isinstance(votes, (int, float)):
            display_info[f'FPTP_{token}'] = f" — {int(votes):,} votes"

    # IRV display info
    irv_result = resblob.get('IRV_result', {})
    irv_winners = resblob.get('IRV_dict', {}).get('winner', [])
    if irv_winners:
        winner_votes = irv_result.get('winner_votes')
        winner_percentage = irv_result.get('winner_percentage')
        for token in irv_winners:
            if winner_votes is not None and winner_percentage is not None:
                display_info[f'IRV_{token}'] = f" — {winner_votes:,} votes ({winner_percentage:.1f}%) in final round"

    # STAR display info
    star_model = resblob.get('scorestardict', {}).get('scoremodel', {})
    star_winner_tokens = star_model.get('winner_tokens', [])

    for token in star_winner_tokens:
        fin1_token = star_model.get('fin1')
        fin2_token = star_model.get('fin2')

        if token == fin1_token:
            votes = star_model.get('fin1votes')
            pct_str = star_model.get('fin1votes_pct_str')
        elif token == fin2_token:
            votes = star_model.get('fin2votes')
            pct_str = star_model.get('fin2votes_pct_str')
        else:
            continue

        if isinstance(votes, (int, float)) and pct_str:
            display_info[f'STAR_{token}'] = f" — {int(votes):,} final-round votes ({pct_str})"

    # Approval display info
    approval_result = resblob.get('approval_result', {})
    approval_counts = approval_result.get('approval_counts', {})
    total_approvals = approval_result.get('total_approvals', 0)

    for token, count in approval_counts.items():
        if isinstance(count, (int, float)) and total_approvals > 0:
            percentage = (count / total_approvals) * 100
            display_info[f'Approval_{token}'] = f" — {int(count):,} approvals ({percentage:.1f}%)"
        elif isinstance(count, (int, float)):
            display_info[f'Approval_{token}'] = f" — {int(count):,} approvals"

    # Condorcet display info
    try:
        from abiflib.pairwise_tally import winlosstie_dict_from_pairdict
        pairdict = resblob.get('pairwise_dict', {})
        wltdict = winlosstie_dict_from_pairdict(candnames, pairdict)

        for token, wlt_data in wltdict.items():
            wins = wlt_data['wins']
            losses = wlt_data['losses']
            ties = wlt_data['ties']
            display_info[f'Condorcet/Copeland_{token}'] = \
                f" — {wins} wins, {losses} losses, {ties} ties"
    except Exception:
        pass

    return display_info


def get_complete_resblob_for_linkpreview(jabmod):
    """Get complete resblob for link preview generation (temporary debug function).

    This follows the same pattern as awt.py election pages to ensure consistency.
    """
    from awt import add_ratings_to_jabmod_votelines

    resconduit = ResultConduit(jabmod=jabmod)
    resconduit = resconduit.update_FPTP_result(jabmod)
    resconduit = resconduit.update_IRV_result(jabmod, include_irv_extra=True)
    resconduit = resconduit.update_pairwise_result(jabmod)

    # For STAR, use rated jabmod just like awt.py does
    ratedjabmod = add_ratings_to_jabmod_votelines(jabmod)
    resconduit = resconduit.update_STAR_result(ratedjabmod)

    resconduit = resconduit.update_approval_result(jabmod)
    return resconduit.resblob
