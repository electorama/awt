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

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ResultConduit:
    jabmod: Dict[str, Any] = field(default_factory=dict)
    resblob: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.jabmod:
            raise TypeError(
                "Please pass in jabmod= param on ResultsConduit init")
        self.resblob = {}

    def update_FPTP_result(self, jabmod) -> "ResultConduit":
        """Add FPTP result to resblob"""
        self.resblob['FPTP_result'] = FPTP_result_from_abifmodel(jabmod)
        self.resblob['FPTP_text'] = get_FPTP_report(jabmod)
        return self

    def update_IRV_result(self, jabmod) -> "ResultConduit":
        self.resblob['IRV_dict'] = IRV_dict_from_jabmod(jabmod)
        self.resblob['IRV_text'] = get_IRV_report(self.resblob['IRV_dict'])
        return self

    def update_pairwise_result(self, jabmod) -> "ResultConduit":
        copecount = full_copecount_from_abifmodel(jabmod)
        cwstring = ", ".join(get_Copeland_winners(copecount))
        self.resblob['copewinnerstring'] = cwstring
        self.resblob['dotsvg_html'] = copecount_diagram(
            copecount, outformat='svg')
        self.resblob['pairwise_dict'] = pairwise_count_dict(jabmod)
        self.resblob['pairwise_html'] = htmltable_pairwise_and_winlosstie(jabmod,
                                                                          snippet=True,
                                                                          validate=True,
                                                                          modlimit=2500)
        return self

    def update_STAR_result(self, jabmod) -> "ResultConduit":
        scorestar = {}
        self.resblob['STAR_html'] = html_score_and_star(jabmod)
        scoremodel = STAR_result_from_abifmodel(jabmod)
        scorestar['scoremodel'] = scoremodel
        stardict = scaled_scores(jabmod, target_scale=50)
        from awt import add_html_hints_to_stardict
        scorestar['starscale'] = \
            add_html_hints_to_stardict(scorestar['scoremodel'], stardict)
        if jabmod['metadata'].get('is_ranking_to_rating'):
            scorestar['star_foot'] = \
                'NOTE: Since ratings or stars are not present in the provided ballots, ' + \
                'allocated stars are estimated using a Borda-like formula.'
        self.resblob['scorestardict'] = scorestar
        return self

    def update_all(self, jabmod):
        '''Call all of the update methods for updating resconduit blob'''
        # This is example code to replace the old _get_jabmod_to_resblob
        resconduit = ResultConduit(jabmod=jabmod)
        resconduit = resconduit.update_FPTP_result(jabmod)
        resconduit = resconduit.update_IRV_result(jabmod)
        resconduit = resconduit.update_pairwise_result(jabmod)
        resconduit = resconduit.update_STAR_result(jabmod)
        return self
