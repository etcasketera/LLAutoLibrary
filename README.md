# LLAutoLibrary
LLAutoLibrary is an automated personal knowledge-graph system designed for researchers. It transforms raw, unstructured documents into a structured, interconnected "Digital Garden" or wiki. By leveraging local LLMs and vector databases, LLAutoLibrary automatically extracts core concepts from your documents and links them together, allowing for efficient discovery and high-fidelity information retrieval.

Inspired by Andrej Karpathy's vision of personal AI operating systems and the potential of LLMs as a reasoning layer over structured data, this project aims to bridge the gap between static document storage and dynamic knowledge management.

## The Vision
The goal of LLAutoLibrary is to move beyond simple folder structures. In a professional or organizational setting, this system allows an LLM to sit atop a massive knowledge graph, enabling it to generate insights, summaries, and reports based on the explicit relationships between data points rather than just raw text chunks.

## Planned Additions
* Linting to clean up overlapping concepts, missing information, and standardizing file formats
* Ability to toggle between local and cloud models
* Containerization
* Additional tools (data visualizations, presentations, reports)
* Improved UI/UX

## Technology Stack
This project is built with a focus on local privacy, high performance, and modern web standards:

* LLM Engine: Ollama running Gemma 4 e4b (or preferred models) locally for privacy-preserving document processing and concept extraction.

* Vector Database: LanceDB used for high-performance vector search to identify and deduplicate concepts across the taxonomy.

* Backend: Python-based engine (engine.py) for document parsing, metadata extraction, and graph construction.

* Frontend: A modern, responsive interface built with React, TypeScript, and Vite, featuring a specialized Research View and Chat interface.

* Data Format: Interoperable Markdown files, structured to be compatible with tools like Obsidian for local-first knowledge management.

## Features
* Automated Parsing: Drop raw PDFs or documents into the /raw folder and let the engine convert them into structured Markdown.

* Concept Extraction: The LLM automatically identifies key themes and creates dedicated "Concept" pages.

* Semantic Linking: Uses vector similarity to link new documents to existing concepts in your library.

* Research View: A dedicated UI for exploring the connections between your sources and extracted knowledge.

## Installation
> If you just want to test the LLM functionality, use testing.ipynb

Follow these steps to set up LLAutoLibrary on your local machine.

Prerequisites
* Python 3.10+

* Node.js (v18+) & npm

* Ollama: Download and install Ollama. Once installed, pull the model:

```Bash
ollama pull gemma4:e4b
```
1. Clone the Repository
```Bash
git clone https://github.com/etcasketera/LLAutoLibrary.git
cd LLAutoLibrary
```
2. Backend Setup (Engine): Create a virtual environment and install the required Python packages (I used conda)


### Windows
```bash
python -m venv venv
.\venv\Scripts\activate
```

### Mac/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```
3. Frontend Setup
Navigate to the frontend directory and install the dependencies:

```bash
cd frontend
npm install
```
4. Running the Project
Start the Engine: Run the Python script to begin processing documents in your /raw folder.

```Bash
python main.py
```
Start the UI: In a new terminal, run the development server:

```Bash
cd frontend
npm run dev
```
Open your browser to the local URL provided by Vite (usually http://localhost:5173).

Acknowledgements & Inspiration
* Andrej Karpathy: For the inspiration regarding the future of personal AI and the "Software 2.0" stack.

* Open-Source Tools: This project is made possible by the incredible communities behind Ollama, LanceDB, React, and the Gemma model family by Google.
