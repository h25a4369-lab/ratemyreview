/* Rate My Review — small progressive enhancements.
   Every page still works without JavaScript; this only improves the experience. */
(function () {
  "use strict";

  /* ---------------------------------------------------------- mobile menu */
  var toggle = document.getElementById("navToggle");
  var panel = document.getElementById("navPanel");

  if (toggle && panel) {
    toggle.addEventListener("click", function () {
      var open = panel.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    });

    // Close the menu after following a link on small screens.
    panel.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.innerWidth <= 900) {
          panel.classList.remove("is-open");
          toggle.setAttribute("aria-expanded", "false");
        }
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && panel.classList.contains("is-open")) {
        panel.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  /* ----------------------------------------------------------- flash notes */
  document.querySelectorAll(".flash").forEach(function (flash) {
    var close = flash.querySelector(".flash-close");
    if (close) {
      close.addEventListener("click", function () {
        flash.remove();
      });
    }
    // Success and info notes fade away on their own after a while.
    if (flash.classList.contains("flash-success") || flash.classList.contains("flash-info")) {
      window.setTimeout(function () {
        flash.style.transition = "opacity .4s ease, transform .4s ease";
        flash.style.opacity = "0";
        flash.style.transform = "translateY(-6px)";
        window.setTimeout(function () { flash.remove(); }, 400);
      }, 7000);
    }
  });

  /* -------------------------------------------------------- confirm delete */
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  /* ----------------------------------------------------------- star picker */
  var picker = document.querySelector(".star-picker");
  var hint = document.getElementById("ratingHint");
  if (picker && hint) {
    var labels = {
      1: "1 star — poor",
      2: "2 stars — below average",
      3: "3 stars — average",
      4: "4 stars — very good",
      5: "5 stars — excellent"
    };
    picker.querySelectorAll("input[type=radio]").forEach(function (input) {
      input.addEventListener("change", function () {
        hint.textContent = labels[input.value] || "Thanks for rating.";
      });
    });
    var checked = picker.querySelector("input:checked");
    if (checked && labels[checked.value]) {
      hint.textContent = labels[checked.value];
    }
  }

  /* ------------------------------------------------------- character count */
  var textarea = document.getElementById("comment");
  var counter = document.getElementById("charCount");
  if (textarea && counter) {
    var update = function () { counter.textContent = String(textarea.value.length); };
    textarea.addEventListener("input", update);
    update();
  }

  /* ------------------------------------------- country / state / place picks */
  // Rebuilds the state list to match the chosen country. Country and state are
  // only helpers for finding a place: the place itself stores both values.
  function cascadeCountryState(countrySelect, stateSelect) {
    if (!countrySelect || !stateSelect) return null;

    var masterStates = Array.prototype.map.call(
      stateSelect.querySelectorAll("option[data-country]"),
      function (option) {
        return { value: option.value, country: option.dataset.country };
      }
    );
    var blankOption = stateSelect.querySelector("option:not([data-country])");

    function rebuild(keepState) {
      stateSelect.innerHTML = "";
      if (blankOption) stateSelect.appendChild(blankOption.cloneNode(true));

      var country = countrySelect.value;
      var seen = {};

      masterStates.forEach(function (state) {
        if (country && state.country !== country) return;
        if (seen[state.value]) return;
        seen[state.value] = true;

        var option = document.createElement("option");
        option.value = state.value;
        option.textContent = state.value;
        option.dataset.country = state.country;
        stateSelect.appendChild(option);
      });

      if (keepState) {
        var exists = Array.prototype.some.call(stateSelect.options, function (option) {
          return option.value === keepState;
        });
        stateSelect.value = exists ? keepState : "";
      }
    }

    return { rebuild: rebuild };
  }

  // Search / browse page: country narrows the state dropdown.
  var filterCountry = document.querySelector("[data-country-filter]");
  var filterState = document.querySelector("[data-state-filter]");
  if (filterCountry && filterState) {
    cascadeCountryState(filterCountry, filterState);
  }

  // Review form: country -> state -> place.
  var reviewCountry = document.getElementById("review-country");
  var reviewState = document.getElementById("review-state");
  var placeSelect = document.getElementById("place_id");

  if (reviewCountry && reviewState && placeSelect) {
    var cascade = cascadeCountryState(reviewCountry, reviewState);

    var filterPlaces = function () {
      var country = reviewCountry.value;
      var state = reviewState.value;

      Array.prototype.forEach.call(placeSelect.options, function (option) {
        if (!option.value) return;
        var matches = (!country || option.dataset.country === country) &&
                      (!state || option.dataset.state === state);
        option.disabled = !matches;
        option.hidden = !matches;
        if (!matches && option.selected) placeSelect.value = "";
      });
    };

    // A place may already be selected (Edit review, or ?place_id= in the URL).
    var chosen = placeSelect.options[placeSelect.selectedIndex];
    if (chosen && chosen.value) {
      reviewCountry.value = chosen.dataset.country || "";
      cascade.rebuild(chosen.dataset.state || "");
    }
    filterPlaces();

    reviewCountry.addEventListener("change", function () {
      cascade.rebuild("");
      filterPlaces();
    });

    reviewState.addEventListener("change", filterPlaces);

    placeSelect.addEventListener("change", function () {
      var option = placeSelect.options[placeSelect.selectedIndex];
      if (!option || !option.value) return;
      reviewCountry.value = option.dataset.country || "";
      cascade.rebuild(option.dataset.state || "");
    });
  }

  /* ------------------------------------------- stop double form submissions */
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector("button[type=submit]");
      if (button && !form.hasAttribute("data-confirm")) {
        window.setTimeout(function () {
          button.disabled = true;
          button.dataset.label = button.textContent;
          button.textContent = "Please wait…";
        }, 0);
      }
    });
  });
})();
