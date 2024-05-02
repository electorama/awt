
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
