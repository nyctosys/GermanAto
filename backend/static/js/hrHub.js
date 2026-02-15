// HR Management hub – back button to home
document.addEventListener("DOMContentLoaded", function () {
  const backBtn = document.getElementById("back-btn");
  if (backBtn) {
    backBtn.href = "/home.html";
    backBtn.addEventListener("click", function (e) {
      e.preventDefault();
      window.location.href = "/home.html";
    });
  }
});
