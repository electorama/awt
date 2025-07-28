const popoverTimeouts = new Map();

/**
 * Shows a popover next to a target element after a short delay.
 *
 * @param {HTMLElement} indicator The element that triggers the popover.
 * @param {function(): string} contentCallback A function that returns the HTML content for the popover.
 */
export function showPopover(indicator, contentCallback) {
    // Clear any existing hide timeout for this indicator
    const hideTimeoutId = popoverTimeouts.get(indicator);
    if (hideTimeoutId) {
        clearTimeout(hideTimeoutId);
        popoverTimeouts.delete(indicator);
    }

    // Find the popover element, which should be a sibling of the indicator.
    const popover = indicator.parentElement.querySelector('.irv-popover');
    if (!popover) {
        console.error('Could not find popover element for indicator:', indicator);
        return;
    }

    // Set a delay before showing the popover
    const showTimeoutId = setTimeout(() => {
        // Populate the popover with content
        popover.innerHTML = contentCallback();

        popover.classList.add('show');
        indicator.classList.add('active');

        // Add mouseenter/mouseleave events to keep popover open when hovering over it
        popover.onmouseenter = () => {
            const hideTimeoutId = popoverTimeouts.get(indicator);
            if (hideTimeoutId) {
                clearTimeout(hideTimeoutId);
                popoverTimeouts.delete(indicator);
            }
        };

        popover.onmouseleave = () => {
            scheduleHidePopover(indicator, popover);
        };
    }, 200); // 200ms delay before showing

    popoverTimeouts.set(indicator, showTimeoutId);
}

/**
 * Hides a popover associated with a target element after a delay.
 *
 * @param {HTMLElement} indicator The element that triggered the popover.
 */
export function hidePopover(indicator) {
    // Clear any existing show timeout
    const showTimeoutId = popoverTimeouts.get(indicator);
    if (showTimeoutId) {
        clearTimeout(showTimeoutId);
        popoverTimeouts.delete(indicator);
    }

    const popover = indicator.parentElement.querySelector('.irv-popover');
    if (popover && popover.classList.contains('show')) {
        scheduleHidePopover(indicator, popover);
    }
}

/**
 * Schedules the hiding of a popover, allowing the user to move their mouse
 * from the indicator to the popover without it disappearing.
 *
 * @param {HTMLElement} indicator The element that triggers the popover.
 * @param {HTMLElement} popover The popover element itself.
 */
function scheduleHidePopover(indicator, popover) {
    const existingHideTimeout = popoverTimeouts.get(indicator);
    if (existingHideTimeout) {
        clearTimeout(existingHideTimeout);
    }

    const hideTimeoutId = setTimeout(() => {
        if (popover) {
            popover.classList.remove('show');
            popover.onmouseenter = null;
            popover.onmouseleave = null;
        }
        indicator.classList.remove('active');
        popoverTimeouts.delete(indicator);
    }, 500); // 500ms delay before hiding

    popoverTimeouts.set(indicator, hideTimeoutId);
}
