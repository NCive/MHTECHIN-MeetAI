// ===============================
// MHTECHIN MeetAI
// Frontend Script
// ===============================

const API = "http://localhost:8000/api";

let token = localStorage.getItem("token") || "";

// ===============================
// Elements
// ===============================

const fileInput = document.getElementById("file");
const fileName = document.getElementById("fname");
const progress = document.getElementById("progress");

const signupBtn = document.getElementById("signupBtn");
const loginBtn = document.getElementById("loginBtn");
const uploadBtn = document.getElementById("uploadFileBtn");

const serverStatus = document.getElementById("serverStatus");
const loginStatus = document.getElementById("loginStatus");

// ===============================
// Health Check
// ===============================

async function checkServer() {

    try {

        const res = await fetch(API + "/health");

        if (!res.ok) throw new Error();

        const data = await res.json();

        serverStatus.innerHTML =
            "🟢 Connected (" + data.model + ")";

    } catch {

        serverStatus.innerHTML =
            "🔴 Backend Offline";

    }

}

checkServer();

// ===============================
// File Selection
// ===============================

fileInput.addEventListener("change", () => {

    if (fileInput.files.length === 0) {

        fileName.innerHTML = "No file selected";

        progress.style.width = "0%";

        progress.innerHTML = "0%";

        return;

    }

    fileName.innerHTML = fileInput.files[0].name;

    progress.style.width = "10%";

    progress.innerHTML = "10%";

});

// ===============================
// Signup
// ===============================

signupBtn.addEventListener("click", async () => {

    const body = {

        name: document.getElementById("name").value,

        email: document.getElementById("email").value,

        password: document.getElementById("password").value

    };

    try {

        const res = await fetch(API + "/auth/signup", {

            method: "POST",

            headers: {

                "Content-Type": "application/json"

            },

            body: JSON.stringify(body)

        });

        const data = await res.json();

        if (!res.ok) {

            loginStatus.innerHTML = data.detail;

            return;

        }

        token = data.access_token;

        localStorage.setItem("token", token);

        loginStatus.innerHTML =
            "✅ Signup Successful";

    }

    catch {

        loginStatus.innerHTML =
            "Unable to connect to server.";

    }

});

// ===============================
// Login
// ===============================

loginBtn.addEventListener("click", async () => {

    const body = {

        email: document.getElementById("email").value,

        password: document.getElementById("password").value

    };

    try {

        const res = await fetch(API + "/auth/login", {

            method: "POST",

            headers: {

                "Content-Type": "application/json"

            },

            body: JSON.stringify(body)

        });

        const data = await res.json();

        if (!res.ok) {

            loginStatus.innerHTML = data.detail;

            return;

        }

        token = data.access_token;

        localStorage.setItem("token", token);

        loginStatus.innerHTML =
            "✅ Login Successful";

    }

    catch {

        loginStatus.innerHTML =
            "Unable to connect to server.";

    }

});

// ===============================
// Upload + Generate MOM
// ===============================

uploadBtn.addEventListener("click", async () => {

    if (!token) {

        alert("Please login first.");

        return;

    }

    if (fileInput.files.length === 0) {

        alert("Select a meeting recording.");

        return;

    }

    const formData = new FormData();

    formData.append("file", fileInput.files[0]);

    progress.style.width = "30%";
    progress.innerHTML = "30%";

    try {

        const res = await fetch(API + "/generate-mom", {

            method: "POST",

            headers: {

                Authorization: "Bearer " + token

            },

            body: formData

        });

        progress.style.width = "80%";
        progress.innerHTML = "80%";

        const data = await res.json();

        if (!res.ok) {

            alert(data.detail);

            progress.style.width = "0%";
            progress.innerHTML = "0%";

            return;

        }

        progress.style.width = "100%";
        progress.innerHTML = "100%";

        loadMeeting(data.mom);

    }

    catch {

        alert("Server Error");

    }

});

// ===============================
// Display AI Output
// ===============================

function loadMeeting(mom) {

    document.getElementById("meetingTitle").innerHTML =
        mom.title;

    document.getElementById("meetingDate").innerHTML =
        mom.date_context;

    document.getElementById("summaryText").innerHTML =
        mom.executive_summary;

    document.getElementById("executiveSummary").innerHTML =
        mom.executive_summary;

    // Participants

    const participants =
        document.getElementById("participantsList");

    participants.innerHTML = "";

    mom.participants.forEach(p => {

        participants.innerHTML +=
            `<li>${p}</li>`;

    });

    // Topics

    const topics =
        document.getElementById("topicsList");

    topics.innerHTML = "";

    mom.topics_discussed.forEach(t => {

        topics.innerHTML +=
            `<li>${t}</li>`;

    });

    // Decisions

    const decisions =
        document.getElementById("decisionsList");

    decisions.innerHTML = "";

    mom.key_decisions.forEach(d => {

        decisions.innerHTML +=
            `<li><strong>${d.decision}</strong><br>${d.rationale}</li>`;

    });

    // Action Items

    const actions =
        document.getElementById("actionList");

    actions.innerHTML = "";

    mom.action_items.forEach(a => {

        actions.innerHTML +=

        `<li>

        <strong>${a.task}</strong><br>

        Owner : ${a.owner}<br>

        Due : ${a.due_date}<br>

        Priority : ${a.priority}

        </li>`;

    });

    // Requirements

    const requirements =
        document.getElementById("requirementsList");

    requirements.innerHTML =

        "<li>Requirements extraction coming soon.</li>";

    // Email

    document.getElementById("emailText").innerHTML =
        "Follow-up email generation coming soon.";

    // Next Steps

    const next =
        document.getElementById("nextStepsList");

    next.innerHTML = "";

    mom.next_steps.forEach(step => {

        next.innerHTML +=
            `<li>${step}</li>`;

    });

}

console.log("Meetingly Frontend Loaded");