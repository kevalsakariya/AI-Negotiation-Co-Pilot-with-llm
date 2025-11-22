import os
import rag_processor 
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv
import requests 
import json     
import base64   

# --- Configuration ---
load_dotenv()
    
# Directories
UPLOAD_DIR = "uploads"
TEMP_DIR = "temp_files"
FRONTEND_DIR = "frontend"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

# --- Load Colab Endpoint from .env ---
COLAB_API_ENDPOINT = os.getenv("COLAB_API_ENDPOINT")
if not COLAB_API_ENDPOINT:
    print("CRITICAL ERROR: 'COLAB_API_ENDPOINT' not found in .env file.")
else:
    print(f"✅ Connected to Colab AI Brain at: {COLAB_API_ENDPOINT}")


# --- API Endpoints ---

@app.route('/status', methods=['GET'])
def get_status():
    if rag_processor.check_index_exists():
        return jsonify({"pdf_processed": True})
    else:
        return jsonify({"pdf_processed": False})

@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    if 'pdf' not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    try:
        pdf_path = os.path.join(UPLOAD_DIR, file.filename)
        file.save(pdf_path)
        print(f"Processing PDF: {pdf_path}")
        rag_processor.create_and_save_vector_store(pdf_path) 
        print("PDF processed and indexed successfully.")
        return jsonify({"message": "PDF processed and indexed successfully!", "pdf_filename": file.filename})
    except Exception as e:
        print(f"Error in /process-pdf: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/process-audio', methods=['POST'])
def process_audio():
    """
    Handles audio upload and sends it to COLAB for transcription.
    """
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
        
    audio_file = request.files['audio']
    
    try:
        print("Audio file received. Sending to Colab for transcription...")
        
        audio_bytes = audio_file.read()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        headers = {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true"
        }
        payload = {
            "task": "transcribe",
            "data": audio_b64
        }
        response = requests.post(COLAB_API_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        
        transcript = response.json().get("transcript")
        print("Transcription complete.")

        return jsonify({"transcript": transcript, "audio_filename": audio_file.filename})

    except Exception as e:
        print(f"Error during audio processing: {e}")
        return jsonify({"error": f"Audio processing failed: {e}"}), 500

# --- THIS IS THE NEW, FLEXIBLE /ask ENDPOINT ---
@app.route('/ask', methods=['POST'])
def ask_question():
    """
    Takes a question and *optional* context (transcript, pdf)
    and streams an answer from the Colab LLM.
    """
    data = request.json
    question = data.get('question')
    transcript = data.get('transcript') # Will be None if skipped
    pdf_indexed = data.get('pdf_indexed', False) # Will be False if skipped

    if not question:
        return jsonify({"error": "Missing question"}), 400

    # We need *at least one* context source
    if not transcript and not pdf_indexed:
        return jsonify({"error": "No context provided. Please upload a PDF or an audio file first."}), 400

    try:
        # --- 1. Build Context (Rules) ---
        context_rules = ""
        if pdf_indexed:
            print("Retrieving relevant rules with LangChain...")
            relevant_chunks = rag_processor.retrieve_relevant_chunks(question)
            if relevant_chunks:
                context_rules = "\n".join(relevant_chunks)
            else:
                context_rules = "No specific rules found related to the question."
            print("Rules retrieved.")
        
        # --- 2. Build Colab Context & Query ---
        colab_context = ""
        colab_query = ""

        if transcript and pdf_indexed:
            # --- BOTH ---
            print("Mode: PDF + Audio")
            colab_context = f"""
[Relevant Rule Clauses]
{context_rules}
"""
            colab_query = f"""
[Negotiation Transcript]
{transcript}

[User's Question]
{question}
"""
        elif pdf_indexed:
            # --- PDF ONLY ---
            print("Mode: PDF Only")
            colab_context = f"""
Answer the user's question based *only* on the following rule clauses.

[Relevant Rule Clauses]
{context_rules}
"""
            colab_query = f"""
[User's Question]
{question}
"""
        elif transcript:
            # --- AUDIO ONLY ---
            print("Mode: Audio Only")
            colab_context = "No rules document was provided. Answer based *only* on the transcript."
            colab_query = f"""
[Negotiat`ion Transcript]
{transcript}

[User's Question]
{question}
"""
        
        # --- 3. Define the streaming function ---
        def stream_response():
            try:
                print("Starting Colab stream proxy...")
                headers = { 
                    "Content-Type": "application/json", 
                    "ngrok-skip-browser-warning": "true"
                }
                payload = {
                    "task": "analyze",
                    "context": colab_context,
                    "query": colab_query
                }
                
                response_stream = requests.post(
                    COLAB_API_ENDPOINT, 
                    headers=headers, 
                    json=payload, 
                    stream=True
                )
                
                if response_stream.status_code != 200:
                    yield f"Error from Colab: {response_stream.text}"
                    return

                for chunk in response_stream.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        yield chunk
                        
                print("Stream proxy complete.")
            except Exception as e:
                print(f"Error during stream generation: {e}")
                yield "Sorry, an error occurred during generation."

        # Return the streaming Response
        return Response(stream_response(), mimetype='text/plain')

    except Exception as e:
        print(f"Error in /ask setup: {e}")
        return jsonify({"error": f"Response generation failed: {e}"}), 500
# --- END OF NEW /ask ENDPOINT ---

@app.route('/reset-index', methods=['POST'])
def reset_index():
    try:
        rag_processor.delete_index()
        return jsonify({"message": "Index reset successfully."})
    except Exception as e:
        print(f"Error in /reset-index: {e}")
        return jsonify({"error": str(e)}), 500

# --- Frontend Serving (Unchanged) ---
@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

# --- Run the App (Unchanged) ---
if __name__ == "__main__":
    print("-------------------------------------------------")
    print("Starting Flask server for AI Co-Pilot...")
    print(f"Flask server starting... Access the app at http://127.0.0.1:5000")
    print("-------------------------------------------------")
    app.run(debug=True, port=5000, use_reloader=False)