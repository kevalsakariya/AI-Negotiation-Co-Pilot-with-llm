document.addEventListener("DOMContentLoaded", () => {
    // --- Global State (Updated) ---
    let appState = {
        transcript: null,
        pdfFilename: null,
        audioFilename: null,
        pdfIndexed: false // <-- NEW: Tracks if PDF was processed
    };

    // --- API URL (Same) ---
    const API_URL = "http://127.0.0.1:5000";

    // --- Element References (Updated) ---
    const pdfForm = document.getElementById("pdf-form");
    const pdfFile = document.getElementById("pdf-file");
    const pdfFileName = document.getElementById("pdf-file-name");
    const pdfStatus = document.getElementById("pdf-status");
    const pdfSummary = document.getElementById("pdf-summary");
    const skipPdfBtn = document.getElementById("skip-pdf-btn"); // <-- NEW

    const audioForm = document.getElementById("audio-form");
    const audioFile = document.getElementById("audio-file");
    const audioFileName = document.getElementById("audio-file-name");
    const audioStatus = document.getElementById("audio-status");
    const skipAudioBtn = document.getElementById("skip-audio-btn"); // <-- NEW

    const chatForm = document.getElementById("chat-form");
    const questionInput = document.getElementById("question-input");
    const chatBox = document.getElementById("chat-box");
    const chatStatus = document.getElementById("chat-status");
    const stopButton = document.getElementById("stop-button");
    const finalSummaryPdf = document.getElementById("final-summary-pdf"); // <-- NEW
    const finalSummaryAudio = document.getElementById("final-summary-audio"); // <-- NEW

    const resetButton = document.getElementById("reset-button");
    const stepper = document.querySelector(".stepper");

    // --- Utility Functions (Same) ---

    // --- Session ID for memory ---
    function getSessionId() {
        let sid = localStorage.getItem('session_id');
        if (!sid) {
            if (typeof crypto !== 'undefined' && crypto.randomUUID) {
                sid = crypto.randomUUID();
            } else {
                sid = 'sid-' + Date.now() + '-' + Math.floor(Math.random() * 1000000);
            }
            localStorage.setItem('session_id', sid);
        }
        return sid;
    }

    function showStep(stepNumber) {
        document.querySelectorAll(".step-content").forEach(content => {
            content.classList.remove("active");
        });
        const activeContent = document.getElementById(`step-${stepNumber}`);
        if (activeContent) {
            activeContent.classList.add("active");
        }
        stepper.querySelectorAll(".step").forEach((step, index) => {
            if ((index + 1) === stepNumber) {
                step.classList.add("active");
            } else {
                step.classList.remove("active");
            }
        });
    }

    function addMessageToChat(role, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}`;
        // Convert newlines from AI to <br> tags
        msgDiv.innerHTML = text.replace(/\n/g, '<br>');
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
        return msgDiv;
    }

    function showStatus(element, message, isError = false) {
        element.textContent = message;
        element.style.color = isError ? "var(--color-error)" : "var(--color-success)";
    }

    // --- Event Listeners (All logic is updated) ---

    (async function checkInitialStatus() {
        try {
            const response = await fetch(`${API_URL}/status`);
            const data = await response.json();
            if (data.pdf_processed) {
                // PDF is already indexed from a previous session
                appState.pdfIndexed = true;
                appState.pdfFilename = "Previously Indexed PDF";
                pdfSummary.textContent = "✅ Rules PDF: Previously Indexed.";
                finalSummaryPdf.textContent = "✅ Rules PDF: Previously Indexed.";
                showStep(2); // Start at audio upload
            } else {
                // Fresh session
                appState.pdfIndexed = false;
                showStep(1);
            }
        } catch (error) {
            console.error("Error checking server status:", error);
            showStatus(pdfStatus, "Could not connect to server.", true);
        }
    })();

    pdfFile.addEventListener("change", () => {
        pdfFileName.textContent = pdfFile.files[0] ? pdfFile.files[0].name : "Click to select a PDF file";
    });

    audioFile.addEventListener("change", () => {
        audioFileName.textContent = audioFile.files[0] ? audioFile.files[0].name : "Click to select an audio file";
    });

    // --- PDF Form Logic (Updated) ---
    pdfForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const file = pdfFile.files[0];
        if (!file) { // User can submit without a file, same as skipping
            skipPdfBtn.click();
            return;
        }
        const formData = new FormData();
        formData.append("pdf", file);
        const submitButton = pdfForm.querySelector("button");
        submitButton.disabled = true;
        showStatus(pdfStatus, "Processing PDF... This may take a moment.");
        try {
            const response = await fetch(`${API_URL}/process-pdf`, {
                method: "POST",
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Unknown error");
            
            appState.pdfFilename = data.pdf_filename;
            appState.pdfIndexed = true; // <-- SET STATE
            
            showStatus(pdfStatus, "✅ PDF processed successfully!", false);
            pdfSummary.textContent = `✅ Rules PDF: ${appState.pdfFilename}`;
            finalSummaryPdf.textContent = `✅ Rules PDF: ${appState.pdfFilename}`; // Update final summary
            
            setTimeout(() => showStep(2), 1000);
        } catch (error) {
            console.error("Error processing PDF:", error);
            showStatus(pdfStatus, `Error: ${error.message}`, true);
        } finally {
            submitButton.disabled = false;
        }
    });

    // --- NEW: Skip PDF Button ---
    skipPdfBtn.addEventListener("click", () => {
        appState.pdfIndexed = false;
        appState.pdfFilename = null;
        pdfSummary.textContent = "📄 Rules PDF: Skipped";
        finalSummaryPdf.textContent = "📄 Rules PDF: Skipped";
        showStep(2);
    });

    // --- Audio Form Logic (Updated) ---
    audioForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const file = audioFile.files[0];
        if (!file) { // User can submit without a file, same as skipping
            skipAudioBtn.click();
            return;
        }
        const formData = new FormData();
        formData.append("audio", file);
        const submitButton = audioForm.querySelector("button");
        submitButton.disabled = true;
        showStatus(audioStatus, "Uploading and transcribing audio... This can take time.");
        try {
            const response = await fetch(`${API_URL}/process-audio`, {
                method: "POST",
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Unknown error");
            
            appState.transcript = data.transcript;
            appState.audioFilename = data.audio_filename;
            
            showStatus(audioStatus, "✅ Audio transcribed successfully!", false);
            finalSummaryAudio.textContent = `✅ Audio File: ${appState.audioFilename}`;
            
            setTimeout(() => showStep(3), 1000);
        } catch (error) {
            console.error("Error processing audio:", error);
            showStatus(audioStatus, `Error: ${error.message}`, true);
        } finally {
            submitButton.disabled = false;
        }
    });

    // --- NEW: Skip Audio Button ---
    skipAudioBtn.addEventListener("click", () => {
        appState.transcript = null;
        appState.audioFilename = null;
        finalSummaryAudio.textContent = "🎵 Audio File: Skipped";
        showStep(3);
    });

    // --- Chat Form Logic (HEAVILY MODIFIED) ---
    // Keep track of the current streaming fetch so we can abort it
    let currentAbortController = null;
    let currentReader = null;

    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const question = questionInput.value.trim();
        if (!question) return;

        // NEW: Check if there is *any* context
        if (!appState.transcript && !appState.pdfIndexed) {
            showStatus(chatStatus, "Error: You must upload a PDF or an Audio file first.", true);
            return;
        }

        addMessageToChat("user", question);
        questionInput.value = ""; // Clear input
        
        const thinkingMessage = addMessageToChat("assistant", "Thinking...");
        
        const submitButton = chatForm.querySelector("button");
        submitButton.disabled = true;

        try {
            // Prepare abort controller so the request can be cancelled
            currentAbortController = new AbortController();

            // Enable stop button while streaming
            stopButton.disabled = false;

            // Send the entire appState to the backend with the abort signal
            const response = await fetch(`${API_URL}/ask`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    question: question,
                    transcript: appState.transcript, // Will be null if skipped
                    pdf_indexed: appState.pdfIndexed, // Will be false if skipped
                    session_id: getSessionId()
                }),
                signal: currentAbortController.signal
            });

            if (!response.ok) {
                const errorData = await response.json(); 
                throw new Error(errorData.error || "Unknown server error");
            }

            // --- Streaming Logic ---
            currentReader = response.body.getReader();
            const decoder = new TextDecoder();

            thinkingMessage.textContent = ""; // Clear "Thinking..."

            while (true) {
                const { value, done } = await currentReader.read();
                if (done) break;

                const textChunk = decoder.decode(value, { stream: true });
                thinkingMessage.innerHTML += textChunk.replace(/\n/g, '<br>'); // Append and format newlines
                chatBox.scrollTop = chatBox.scrollHeight;
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                thinkingMessage.innerHTML += '<br><em>Generation stopped.</em>';
            } else {
                console.error("Error asking question:", error);
                thinkingMessage.innerHTML = `Sorry, an error occurred: ${error.message}`;
            }
        } finally {
            // Clean up
            submitButton.disabled = false;
            questionInput.focus();
            stopButton.disabled = true;
            try { currentAbortController = null; } catch(e){}
            try { currentReader = null; } catch(e){}
        }
    });

    // Stop button handler: tell server to stop, then abort local fetch
    stopButton.addEventListener('click', async () => {
        const sid = getSessionId();
        try {
            // Ask backend to stop generation for this session
            fetch(`${API_URL}/stop`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sid })
            }).catch(() => {});
        } catch (e) {
            // ignore
        }

        // Abort local streaming fetch if present
        try {
            if (currentAbortController) currentAbortController.abort();
        } catch (e) {
            console.error('Error aborting request:', e);
        }

        stopButton.disabled = true;
    });

    // --- Reset Button Logic (Updated) ---
    resetButton.addEventListener("click", async () => {
        if (!confirm("Are you sure? This will delete the current rules index and restart the app.")) {
            return;
        }
        try {
            const response = await fetch(`${API_URL}/reset-index`, { method: "POST" });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Unknown error");
            alert("App reset. You can now upload a new PDF.");
            window.location.reload();
        } catch (error) {
            console.error("Error resetting index:", error);
            alert(`Could not reset app: ${error.message}`);
        }
    });
});