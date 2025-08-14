
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
  const longFormRadio = document.getElementById('long-form-mode');
  const tabbedRadio = document.getElementById('tabbed-mode');
  const resultsContainer = document.querySelector('.results-container');
  const methodTabs = document.querySelectorAll('.method-tab');
  
  if (!longFormRadio || !tabbedRadio || !resultsContainer) return;
  
  // Function to switch between long-form and tabbed view
  function updateViewMode() {
    if (tabbedRadio.checked) {
      resultsContainer.classList.add('tabbed-mode');
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
      // Remove any method-section classes we added
      document.querySelectorAll('.method-section').forEach(section => {
        section.classList.remove('visible');
      });
    }
  }
  
  // Function to show the section corresponding to the active tab
  function showActiveMethodSection() {
    if (!resultsContainer.classList.contains('tabbed-mode')) return;
    
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
  
  // Add event listeners
  longFormRadio.addEventListener('change', updateViewMode);
  tabbedRadio.addEventListener('change', updateViewMode);
  
  // Update tab click behavior for tabbed mode
  methodTabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
      if (tabbedRadio.checked) {
        e.preventDefault();
        
        // Remove active from all tabs
        methodTabs.forEach(t => t.classList.remove('active'));
        // Add active to clicked tab
        tab.classList.add('active');
        
        // Show corresponding section
        setTimeout(showActiveMethodSection, 10);
        
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

const tabLinks = document.querySelectorAll('.tab-links li');
const tabContent = document.querySelectorAll('.tab-content');

tabLinks.forEach(link => {
  link.addEventListener('click', () => {
    // Remove active states
    tabLinks.forEach(li => li.classList.remove('active'));
    tabContent.forEach(content => content.classList.remove('active'));

    // Activate clicked tab and content
    const target = link.dataset.target;
    link.classList.add('active');
    document.getElementById(target).classList.add('active');
  });
});

window.addEventListener('DOMContentLoaded', () => {
  tabContent.forEach(content => {
    content.classList.remove('active');
  });
  tabLinks[0].classList.add('active');
  tabContent[0].classList.add('active');
});
