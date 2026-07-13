// ===============================
// AI Client Meeting MOM Generator
// ===============================

// Get Started Button
const getStartedBtn = document.getElementById("getStartedBtn");

if (getStartedBtn) {
    getStartedBtn.addEventListener("click", function () {
        document.getElementById("features").scrollIntoView({
            behavior: "smooth"
        });
    });
}

// Navbar Active Link
const navLinks = document.querySelectorAll(".nav-link");

navLinks.forEach(link => {
    link.addEventListener("click", function () {

        navLinks.forEach(item => item.classList.remove("active"));

        this.classList.add("active");
    });
});

// Feature Card Animation
const cards = document.querySelectorAll(".feature-card");

cards.forEach(card => {

    card.addEventListener("mouseenter", function () {
        card.style.transform = "translateY(-10px)";
        card.style.transition = "0.3s";
    });

    card.addEventListener("mouseleave", function () {
        card.style.transform = "translateY(0)";
    });

});

// Welcome Message
window.addEventListener("load", () => {
    console.log("Welcome to AI Client Meeting MOM Generator");
});