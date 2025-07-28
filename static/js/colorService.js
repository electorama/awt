// File: static/js/colorService.js

let candidateColors = {};

/**
 * Initializes the color service by reading data from the main results container.
 */
export function initialize() {
    const container = document.getElementById('results-container');
    if (container && container.dataset.candidateColors) {
        try {
            candidateColors = JSON.parse(container.dataset.candidateColors);
        } catch (e) {
            console.error("Failed to parse candidate colors data:", e);
            candidateColors = {};
        }
    }
}

/**
 * Gets the color for a specific candidate.
 * @param {string} candidateKey - The key for the candidate.
 * @returns {string} The hex color code or a default fallback color.
 */
export function getColor(candidateKey) {
    return candidateColors[candidateKey] || '#dddddd'; // Default grey
}
