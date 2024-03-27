function pushTextFromID(exampleID) {
  var exampleText = document.getElementById(exampleID).value;
  document.getElementById("abifinput").value = exampleText;
  document.getElementById("ABIF_submission_area").scrollIntoView({behavior: "smooth"});
}
