import { showPopover, hidePopover } from './popover.js';
import { getColor } from './colorService.js';

let roundsData = [];
let candidateNames = {};

/**
 * Initializes the IRV display module with data from the page.
 */
export function initializeIrvDisplay() {
    const container = document.getElementById('irv-display-container');
    if (!container) {
        console.log('IRV display container not found. Skipping initialization.');
        return;
    }

    try {
        roundsData = JSON.parse(container.dataset.roundsData);
        candidateNames = JSON.parse(container.dataset.candidateNames);
    } catch (e) {
        console.error('Failed to parse IRV data from container:', e);
        return;
    }

    // Add event listeners for popovers
    container.querySelectorAll('.irv-transfer-indicator').forEach(indicator => {
        const roundIndex = parseInt(indicator.dataset.roundIndex, 10);
        const candidateKey = indicator.dataset.candidateKey;

        indicator.addEventListener('mouseover', () => {
            showPopover(indicator, () => getIrvPopoverContent(roundIndex, candidateKey));
        });
        indicator.addEventListener('mouseout', () => {
            hidePopover(indicator);
        });
    });

    // Initialize data bars
    initializeDataBars();
}

/**
 * Generates the HTML content for the IRV popover.
 * @param {number} roundIndex The index of the round.
 * @param {string} candidateKey The key for the candidate.
 * @returns {string} The HTML content for the popover.
 */
function getIrvPopoverContent(roundIndex, candidateKey) {
    const roundData = roundsData[roundIndex];
    const candidateName = candidateNames[candidateKey] || candidateKey;

    if (!roundData) {
        return '<div>No data available for this round.</div>';
    }

    let content = '';
    let hasContent = false;
    const isFinalRound = (roundIndex + 1) === roundsData.length;

    // Check actual transfers
    if (roundData.transfers && roundData.transfers[candidateKey]) {
        const transferLabel = isFinalRound ?
            `Second choices in final round on ballots listing ${candidateName} first:` :
            `Transfer of ${candidateName}'s votes:`;
        content += `<div style="margin-bottom: 8px;"><strong>${transferLabel}</strong></div>`;
        content += formatCandidateSecondChoices(roundData.transfers[candidateKey]);
        hasContent = true;
    }

    // Check hypothetical transfers
    if (roundData.hypothetical_transfers && roundData.hypothetical_transfers[candidateKey]) {
        if (hasContent) {
            content += '<hr style="margin: 8px 0;">';
        }
        const hypotheticalLabel = `Remaining second choices in round ${roundIndex + 1} on ballots listing ${candidateName} first:`;
        content += `<div style="margin-bottom: 8px;"><strong>${hypotheticalLabel}</strong></div>`;
        content += formatCandidateSecondChoices(roundData.hypothetical_transfers[candidateKey]);
        hasContent = true;
    }

    if (!hasContent) {
        content = `<div>No transfer data available for ${candidateName} in Round ${roundIndex + 1}.</div>`;
    }

    return content;
}

/**
 * Formats the second-choice transfer data into HTML.
 * @param {object} transfers The transfer data object.
 * @returns {string} HTML representation of the transfers.
 */
function formatCandidateSecondChoices(transfers) {
    let html = '';
    let totalVotes = 0;

    if (typeof transfers !== 'object' || transfers === null) {
        return `<div>${transfers}</div>`;
    }

    const transferArray = Object.entries(transfers).map(([dest, amount]) => {
        const votes = (typeof amount === 'object' && amount.votes !== undefined) ? amount.votes : parseInt(amount) || 0;
        totalVotes += votes;
        const destName = candidateNames[dest] || dest;
        const color = getColor(dest) || '#999';
        const isExhausted = dest === 'exhausted' || destName.toLowerCase().includes('exhausted');
        const percentage = (typeof amount === 'object' && amount.percentage) ? `${amount.percentage}%` : '';
        return { destination: destName, votes, percentage, color, isExhausted };
    });

    transferArray.sort((a, b) => {
        if (a.isExhausted !== b.isExhausted) return a.isExhausted ? 1 : -1;
        return b.votes - a.votes;
    });

    transferArray.forEach(transfer => {
        const colorBox = `<span style="display: inline-block; width: 12px; height: 12px; background-color: ${transfer.color}; border: 1px solid #333; margin-right: 6px; vertical-align: middle;"></span>`;
        const percentageStr = transfer.percentage ? ` (${transfer.percentage})` : '';
        const label = transfer.isExhausted ? `Exhausted: ${transfer.votes}` : `${transfer.votes} → ${transfer.destination}`;
        html += `<div style="margin-left: 15px; margin-bottom: 2px; font-size: 11px;">${colorBox}${label}${percentageStr}</div>`;
    });

    html += `<div style="margin-top: 8px; font-weight: bold; font-size: 11px;">Total: ${totalVotes} ballots</div>`;
    return html;
}

/**
 * Creates and injects the data bars into the transfer indicators.
 */
function initializeDataBars() {
    roundsData.forEach((roundData, roundIndex) => {
        document.querySelectorAll(`.irv-transfer-indicator[data-round-index="${roundIndex}"]`).forEach(indicator => {
            const candidateKey = indicator.dataset.candidateKey;
            const transferData = (roundData.transfers && roundData.transfers[candidateKey]) ||
                                 (roundData.hypothetical_transfers && roundData.hypothetical_transfers[candidateKey]);

            if (transferData) {
                const dataBarHTML = createDataBar(transferData);
                const arrowHTML = '<div class="transfer-arrow">→</div>';
                indicator.innerHTML = dataBarHTML + arrowHTML;
            }
        });
    });
}

/**
 * Creates the HTML for a single data bar based on transfer data.
 * @param {object} transfers The transfer data.
 * @returns {string} The HTML for the data bar.
 */
function createDataBar(transfers) {
    let totalVotes = 0;
    const segments = [];

    if (typeof transfers !== 'object' || transfers === null) return '';

    Object.values(transfers).forEach(amount => {
        totalVotes += (typeof amount === 'object' && amount.votes !== undefined) ? amount.votes : parseInt(amount) || 0;
    });

    if (totalVotes === 0) return '';

    Object.entries(transfers).forEach(([dest, amount]) => {
        const votes = (typeof amount === 'object' && amount.votes !== undefined) ? amount.votes : parseInt(amount) || 0;
        if (votes > 0) {
            const percentage = (votes / totalVotes) * 100;
            const color = getColor(dest) || '#999';
            const destName = candidateNames[dest] || dest;
            const isExhausted = dest === 'exhausted' || destName.toLowerCase().includes('exhausted');
            segments.push({ votes, percentage, color, isExhausted });
        }
    });

    segments.sort((a, b) => {
        if (a.isExhausted !== b.isExhausted) return a.isExhausted ? 1 : -1;
        return b.votes - a.votes;
    });

    const segmentsHTML = segments.map(segment =>
        `<div style="background-color: ${segment.color}; width: ${segment.percentage}%; height: 100%; display: inline-block;"></div>`
    ).join('');

    return `<div class="data-bar">${segmentsHTML}</div>`;
}
