const buttons = document.querySelectorAll(".filters button");
buttons.forEach((button) => {
  button.addEventListener("click", () => {
    buttons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
  });
});
