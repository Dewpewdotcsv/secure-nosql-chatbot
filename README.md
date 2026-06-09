# Secure NoSQL Chatbot

A secure natural language query gateway that translates conversational questions into standard MongoDB Query using LangGraph and LLMs. 

The project contains two versions:
1. **Secure Gateway (`app_enterprise.py`)**: Features advanced security guards including dynamic field obfuscation and value tokenization, preventing private data leakage when calling external LLMs.
2. **Local CLI (`app_local_cli.py`)**: A security-free offline version that translates English queries into MongoDB commands using a local Llama 3.1 model via Ollama.

---

## Features

- **Natural Language to NoSQL**: Queries MongoDB collections using conversational English.
- **Dynamic Field Mapping**: Swaps real database field names with randomized placeholders to hide structure details.
- **Token Swapping**: Replaces sensitive data like emails and numbers with placeholders before sending prompts to cloud AI engines.
- **Self-Healing Loop**: Automatically intercepts query runtime errors and queries the LLM again for self-correction.
- **Interactive UI**: Clean React-based web dashboard to execute database lookups.

---

## Project Structure

```
├── app_enterprise.py       # Primary Secure LangGraph Agent CLI
├── app_local_cli.py       # Offline local Llama 3.1 LangGraph Agent CLI
├── db_initializer.py      # Seed script for MongoDB and Authentication collections
├── backend.py             # FastAPI backend server linking app_enterprise.py to UI
├── requirements.txt       # Python project dependencies
├── .gitignore             # Config to protect credentials and caches
└── Frontend/              # React (Vite, Tailwind, Shadcn) UI dashboard codebase
```

---

## Installation

### Prerequisites
- Python 3.9+
- Node.js (for running the React Frontend)
- Ollama running locally with Llama 3.1 (`ollama run llama3.1:8b`)

### Setup Environment
1. Clone the repository and install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file in the root directory:
   ```env
   MONGO_URI=your_mongodb_connection_uri
   GROQ_API_KEY=your_optional_groq_api_key_for_faster_translation
   ```
3. Initialize and seed the MongoDB database:
   ```bash
   python db_initializer.py
   ```

---

## How to Run

### Option 1: Run local offline CLI Chatbot
```bash
python app_local_cli.py
```

### Option 2: Run Secure CLI Gateway
```bash
python app_enterprise.py
```

### Option 3: Run the Web Dashboard Portal
1. ```bash
   python backend.py
   ```
2. ```bash
   cd Frontend
   npm install
   npm run dev
   ```
3. Open `http://localhost:5173` in browser.
