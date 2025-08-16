
function toggleShowHide(param) {
  showHideElem = document.getElementById('abifshowhide');
  targetClassList = document.getElementById(param.target).classList;
  if (targetClassList.contains('active')) {
    showHideElem.innerHTML = 'show';
    targetClassList.remove('active');
  } else {
    showHideElem.innerHTML = 'hide';
    targetClassList.add('active');
  }
}

// Method tab activation for UX Step 4
function activateMethodTab() {
  // Remove active class from all tabs
  document.querySelectorAll('.method-tab').forEach(tab => {
    tab.classList.remove('active');
  });

  // Add active class to current tab based on URL hash
  const hash = window.location.hash;
  if (hash) {
    const activeTab = document.querySelector(`a[href="${hash}"].method-tab`);
    if (activeTab) {
      activeTab.classList.add('active');
    }
  }
}

// Initialize tab activation on page load and hash change
document.addEventListener('DOMContentLoaded', activateMethodTab);
window.addEventListener('hashchange', activateMethodTab);

// UX Step 5: Tabbed view mode functionality
function initializeTabbedMode() {
  const tabbedToggle = document.getElementById('tabbed-mode');
  const resultsContainer = document.querySelector('.results-container');
  const methodTabs = document.querySelectorAll('.method-tab');

  if (!tabbedToggle || !resultsContainer) return;

  // Function to switch between long-form and tabbed view
  function updateViewMode() {
    const methodTabs = document.querySelector('.method-tabs');

    if (tabbedToggle.checked) {
      resultsContainer.classList.add('tabbed-mode');
      // Show tabs
      if (methodTabs) {
        methodTabs.classList.remove('hidden-tabs');
      }
      // If no tab is active, activate the first one
      if (!document.querySelector('.method-tab.active')) {
        const firstTab = document.querySelector('.method-tab');
        if (firstTab) {
          firstTab.classList.add('active');
        }
      }
      showActiveMethodSection();
    } else {
      resultsContainer.classList.remove('tabbed-mode');
      // Hide tabs
      if (methodTabs) {
        methodTabs.classList.add('hidden-tabs');
      }
      // Remove any method-section classes we added
      document.querySelectorAll('.method-section').forEach(section => {
        section.classList.remove('visible');
      });
    }
  }

  // Function to show the section corresponding to the active tab
  function showActiveMethodSection() {
    // Call the global function
    showActiveMethodSectionGlobal();
  }

  // Add event listeners
  tabbedToggle.addEventListener('change', updateViewMode);

  // Update tab click behavior for tabbed mode
  methodTabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
      if (tabbedToggle.checked) {
        e.preventDefault();

        // Remove active from all tabs
        methodTabs.forEach(t => t.classList.remove('active'));
        // Add active to clicked tab
        tab.classList.add('active');

        // Show corresponding section
        setTimeout(showActiveMethodSectionGlobal, 10);

        // Update URL hash
        const href = tab.getAttribute('href');
        if (href) {
          window.location.hash = href;
        }
      }
    });
  });

  // Initialize view mode
  updateViewMode();
}

// Initialize tabbed mode functionality
document.addEventListener('DOMContentLoaded', initializeTabbedMode);

// Handle winner table links for both tabbed and long-form modes
function handleWinnerTableLinks() {
  const methodLinks = document.querySelectorAll('.method-link');

  methodLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      const tabbedToggle = document.getElementById('tabbed-mode');
      const href = link.getAttribute('href').substring(1); // Remove #

      if (tabbedToggle && tabbedToggle.checked) {
        // In tabbed mode: prevent default, activate tab, and show content
        e.preventDefault();

        // Find and activate the corresponding tab
        const targetTab = document.querySelector(`a[href="#${href}"].method-tab`);
        if (targetTab) {
          // Remove active from all tabs
          document.querySelectorAll('.method-tab').forEach(tab => {
            tab.classList.remove('active');
          });

          // Activate the target tab
          targetTab.classList.add('active');

          // Show the corresponding section
          showActiveMethodSectionGlobal();

          // Update URL hash
          window.location.hash = `#${href}`;
        }
      }
      // In long-form mode: let the default behavior work (scroll to section)
    });
  });
}

// Function to show active method section (needed for winner table links)
function showActiveMethodSectionGlobal() {
  const resultsContainer = document.querySelector('.results-container');
  if (!resultsContainer || !resultsContainer.classList.contains('tabbed-mode')) return;

  // Hide all sections first
  document.querySelectorAll('.method-section').forEach(section => {
    section.classList.remove('visible');
  });

  // Find active tab and show corresponding section
  const activeTab = document.querySelector('.method-tab.active');
  if (activeTab) {
    const href = activeTab.getAttribute('href').substring(1); // Remove #
    const targetSection = document.getElementById(href + '-section') ||
                         document.querySelector(`[data-method="${href}"]`) ||
                         document.querySelector(`a[name="${href}"]`)?.closest('.method-section');

    if (targetSection) {
      targetSection.classList.add('visible');
    }
  }
}

document.addEventListener('DOMContentLoaded', handleWinnerTableLinks);

function pushTextFromID(exampleID) {
  var exampleText = document.getElementById(exampleID).value;
  document.getElementById("abifbox").classList.add('active');
  document.getElementById("abifinput").value = exampleText;
  document.getElementById("ABIF_submission_area").scrollIntoView({behavior: "smooth"});
  document.getElementById("submitButton").classList.add("throbbing");
  setTimeout(function() {
    document.getElementById("submitButton").classList.remove("throbbing");
  }, 3000);
}

// Homepage vertical tabs functionality (separate from results page tabbed view)
// These handle the vertical tabs on the homepage examples section
const homepageTabLinks = document.querySelectorAll('.tab-links li');
const homepageTabContent = document.querySelectorAll('.tab-content');

homepageTabLinks.forEach(link => {
  link.addEventListener('click', () => {
    // Remove active states from all homepage tabs
    homepageTabLinks.forEach(li => li.classList.remove('active'));
    homepageTabContent.forEach(content => content.classList.remove('active'));

    // Activate clicked tab and corresponding content
    const target = link.dataset.target;
    link.classList.add('active');
    const targetContent = document.getElementById(target);
    if (targetContent) {
      targetContent.classList.add('active');
    }
  });
});

// Initialize homepage tabs on page load
window.addEventListener('DOMContentLoaded', () => {
  // Only initialize if we're on a page with homepage tabs
  if (homepageTabContent.length > 0) {
    // Remove active from all content areas first
    homepageTabContent.forEach(content => {
      content.classList.remove('active');
    });

    // Activate first tab and content
    if (homepageTabLinks.length > 0) {
      homepageTabLinks[0].classList.add('active');
    }
    if (homepageTabContent.length > 0) {
      homepageTabContent[0].classList.add('active');
    }
  }
});
