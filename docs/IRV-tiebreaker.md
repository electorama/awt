# IRV Tiebreaker Implementation for future release (0.34? 0.35?)

## Problem Statement

In v0.33.0, abiftool uses `random.choice()` for IRV elimination ties,
creating non-deterministic results that break caching and
auditability. DPL2003 demonstrates this issue where Round 3 has Bdale
Garbee and Martin Michlmayr tied at 146 votes, leading to different
winners depending on which candidate is randomly eliminated.

## Real-World IRV Tiebreaker Rules

### Common Legal Approaches

1. **Lot Drawing** (California, San Francisco)
   - Physical process (drawing names, coin flip, dice)
   - Predetermined by election officials
   - Documented and auditable
   - Applied consistently across all counting

2. **Previous Round Performance** (Minneapolis, many academic implementations)
   - Candidate with fewer votes in previous round eliminated first
   - Deterministic and explainable
   - Reflects voter preference trends

3. **Initial Round Performance** (Some Australian jurisdictions)
   - Candidate with fewer first-choice votes eliminated first
   - Simple to understand and implement

4. **Cascade Tiebreakers** (Ireland, some U.S. jurisdictions)
   - Multiple rules applied in order
   - Example: Previous round → Initial round → Alphabetical

## Implementation Options for 0.34

### Option 1: Simulated Deterministic Lot Drawing
```python
def deterministic_lot_draw(tied_candidates, election_context):
    """Simulate predetermined lot drawing using election data hash"""
    # Use election title + candidate names to create reproducible "lot"
    seed_data = f"{election_context['title']}:{':'.join(sorted(tied_candidates))}"
    hash_result = hashlib.sha256(seed_data.encode()).hexdigest()
    # Use hash to deterministically select winner
    index = int(hash_result[:8], 16) % len(tied_candidates)
    return tied_candidates[index]
```

**Pros:** Legally accurate (simulates random selection), reproducible, auditable
**Cons:** Still appears "random" to users, requires careful documentation

### Option 2: Configurable Tiebreaker Rules
```python
class IRVTiebreaker:
    def __init__(self, rules=['previous_round', 'initial_round', 'alphabetical']):
        self.rules = rules
    
    def resolve_tie(self, tied_candidates, round_history):
        for rule in self.rules:
            result = self._apply_rule(rule, tied_candidates, round_history)
            if result:
                return result
        # Final fallback
        return tied_candidates[0]
```

**Pros:** Flexible, can match different jurisdictions, transparent
**Cons:** More complex, may not match legal requirements for random selection

### Option 3: Ghost Candidates (Multiple Winners)
```python
def irv_with_ghost_candidates(ballots):
    """Return all possible IRV outcomes when ties exist"""
    # Track all possible elimination paths
    # Return tree structure with multiple winners
    # Requires significant architectural changes
```

**Pros:** Shows all possible outcomes, most informative for analysis
**Cons:** Major architectural change, complex UI requirements, performance impact

## Implementation Plan for 0.34

### Phase 1: Research and Design
1. **Survey real jurisdictions** - Document actual tiebreaker rules used
2. **Legal analysis** - Understand requirements for different regions
3. **User experience design** - How to display tiebreaker information
4. **Performance analysis** - Impact of different approaches on computation time

### Phase 2: Core Implementation
1. **Modify IRV core logic** in `abiflib/irv_tally.py`
2. **Add tiebreaker configuration** to ABIF metadata format
3. **Update JSON output format** to include tiebreaker information
4. **Add notices system** for tiebreaker explanations

### Phase 3: Web Interface
1. **Template updates** to display tiebreaker information
2. **Interactive elements** for ghost candidates (if implemented)
3. **Configuration interface** for tiebreaker rules
4. **Documentation updates** for users

### Phase 4: Testing and Migration
1. **Regression testing** - Ensure non-tied elections unchanged
2. **Migration strategy** - Handle existing cached results
3. **Performance testing** - Verify scalability with large elections
4. **User acceptance testing** - Gather feedback on new interface

## Data Structure Changes Required

### Enhanced IRV Round Data
```json
{
  "roundnum": 3,
  "tied_candidates": ["BdaleGarbee", "MartinMichlmayr"],
  "tie_resolution": {
    "method": "deterministic_lot",
    "eliminated": "BdaleGarbee",
    "explanation": "Simulated lot drawing based on election data hash",
    "alternative_outcomes": ["MartinMichlmayr_wins", "BdaleGarbee_wins"]
  },
  "tiebreaker_metadata": {
    "jurisdiction": "California",
    "rule_source": "Elections Code Section 15626"
  }
}
```

### ABIF Metadata Extensions
```json
{
  "metadata": {
    "tiebreaker_rules": ["deterministic_lot", "previous_round", "alphabetical"],
    "jurisdiction": "San Francisco, CA",
    "legal_citation": "California Elections Code Section 15626"
  }
}
```

## Open Questions

1. **Legal Compliance**: Should abiftool prioritize legal accuracy (simulated random) or analytical utility (deterministic rules)?

2. **Configuration vs. Detection**: Should tiebreaker rules be manually configured per election, or auto-detected based on jurisdiction metadata?

3. **Backward Compatibility**: How do we handle elections that have already been cached with random tiebreakers? Migration strategy?

4. **Performance vs. Features**: Ghost candidates could show all possible outcomes, but at what computational cost for large elections?

5. **User Interface Complexity**: How much tiebreaker detail should be shown by default vs. hidden in expandable sections?

6. **Metadata Standards**: Should we establish a standard vocabulary for tiebreaker rules that other election analysis tools could adopt?

7. **Multi-Stage Ties**: How do we handle cascading ties (Round 3 tie affects Round 4, which has its own tie)?

8. **Validation Requirements**: Should abiftool validate that the specified tiebreaker rules are legally appropriate for the declared jurisdiction?

9. **International Support**: How do we handle the wide variety of international IRV tiebreaker rules (Australia, Ireland, etc.)?

10. **Documentation Strategy**: Should tiebreaker explanations be embedded in templates or generated as separate documentation?

11. **Testing Edge Cases**: What's the most complex tie scenario we need to support (3-way ties, multiple consecutive tied rounds)?

12. **Caching Strategy**: How do we structure caching to handle different tiebreaker configurations for the same election data?

## Bibliography and Legal References

### United States Jurisdictions

**California (San Francisco)**
- California Elections Code Section 15626: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=ELEC&sectionNum=15626
- San Francisco Charter Section 13.102: https://sfbos.org/sites/default/files/Charter.pdf
- San Francisco Department of Elections RCV Rules: https://www.sfelections.org/tools/election_data/

**Minnesota (Minneapolis)**
- Minneapolis City Charter Section 8.2: https://www.minneapolismn.gov/government/city-charter/
- Minnesota Statutes Section 204B.12: https://www.revisor.mn.gov/statutes/cite/204B.12
- Minneapolis RCV Implementation Guide: https://vote.minneapolismn.gov/ranked-choice-voting/

**Maine**
- Maine Revised Statutes Title 21-A Chapter 9-A: https://legislature.maine.gov/statutes/21-A/title21-Ach9-Asec0sec737-A.html
- Maine Secretary of State RCV Rules: https://www.maine.gov/sos/cec/elec/upcoming/rcv.html

### International Jurisdictions

**Australia (Federal)**
- Commonwealth Electoral Act 1918 Section 273: https://www.legislation.gov.au/Details/C2022C00327
- Australian Electoral Commission RCV Guidelines: https://www.aec.gov.au/voting/counting/files/counting-senate-ballot-papers.pdf
- Electoral Regulations 2017: https://www.legislation.gov.au/Details/F2017L00487

**Australia (New South Wales)**
- Electoral Act 2017 (NSW) Section 6.27: https://legislation.nsw.gov.au/view/html/inforce/current/act-2017-066
- NSW Electoral Commission Procedures: https://www.elections.nsw.gov.au/Elections/How-voting-works/Preferential-voting

**Ireland**
- Electoral Act 1992 Schedule 2: https://www.irishstatutebook.ie/eli/1992/act/23/enacted/en/html
- Electoral (Amendment) Act 2001: https://www.irishstatutebook.ie/eli/2001/act/38/enacted/en/html
- Department of Housing Guidelines: https://www.housing.gov.ie/local-government/voting/local-elections/counting-votes-local-elections

**United Kingdom (Scotland)**
- Local Government Elections (Scotland) Order 2007: https://www.legislation.gov.uk/ssi/2007/42/contents/made
- Electoral Management Board Scotland Guidance: https://www.emb-scotland.org.uk/

### Academic and Research Sources

**FairVote Research**
- IRV Tiebreaker Analysis: https://fairvote.org/research_irtbreaking/
- International RCV Practices: https://fairvote.org/research_rcvpractices/

**Electoral Reform Society (UK)**
- STV Counting Rules: https://www.electoral-reform.org.uk/latest-news-and-research/publications/how-to-conduct-an-election-by-the-single-transferable-vote/

**Proportional Representation Society of Australia**
- Comparative Tiebreaker Study: https://www.prsa.org.au/papers/tiebreakers.htm

### Technical Implementation References

**Open Source RCV Software**
- OpenSTV Tiebreaker Implementation: https://github.com/Conservatory/openstv/
- RankedVote.co Technical Documentation: https://www.rankedvote.co/guides/implementation/

**Election Audit Resources**
- USENIX Election Auditing Papers: https://www.usenix.org/conference/evtwote/
- Verified Voting Foundation: https://verifiedvoting.org/