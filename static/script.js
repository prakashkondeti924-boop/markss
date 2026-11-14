document.addEventListener("DOMContentLoaded", function () {
  var menuToggle = document.getElementById("menuToggle");
  var sidebar = document.getElementById("sidebar");

  if (menuToggle && sidebar) {
    menuToggle.addEventListener("click", function () {
      var isOpen = sidebar.classList.toggle("sidebar-open");
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    document.addEventListener("click", function (event) {
      if (!sidebar.contains(event.target) && !menuToggle.contains(event.target)) {
        sidebar.classList.remove("sidebar-open");
        menuToggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.querySelectorAll("[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll(".flash-close").forEach(function (button) {
    button.addEventListener("click", function () {
      var message = button.closest(".flash");
      if (message) {
        message.remove();
      }
    });
  });

  var recordClass = document.getElementById("recordClass");
  var recordSection = document.getElementById("recordSection");
  if (recordClass && recordSection) {
    recordClass.addEventListener("change", function () {
      recordSection.value = "";
      recordSection.form.submit();
    });
  }

  var rankingClass = document.getElementById("rankingClass");
  var rankingSection = document.getElementById("rankingSection");
  if (rankingClass && rankingSection) {
    rankingClass.addEventListener("change", function () {
      rankingSection.value = "";
    });
  }
});
