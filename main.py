import os
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Path as FastApiPath
from pydantic import BaseModel
import uvicorn
import re
from typing import List
import pandas as pd

# Import your working classes from the refactored file
from engine import (
    ManifestManager, LibrarianIngester, Librarian, 
    FileManagement, TaxonomySearcher, LibrarianResearcher
)

class ExplorationRequest(BaseModel):
    question: str
    answer: str
    sources: List[str]

app = FastAPI(title="Librarian API", version="1.0")

# Allow React frontend to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBAL INITIALIZATION ---
BASE_DIR = Path(".")
RAW_DIR = BASE_DIR / "raw"
WIKI_DIR = BASE_DIR / "wiki"
MANIFEST_PATH = BASE_DIR / "manifest.json"

# Initialize your existing classes
manifest = ManifestManager(MANIFEST_PATH)
ingester = LibrarianIngester()
model = Librarian()
filer = FileManagement(WIKI_DIR)
taxsearcher = TaxonomySearcher()
researcher = LibrarianResearcher(WIKI_DIR)

# --- BACKGROUND TASK LOGIC ---
def process_document(file_path: Path):
    """The heavy lifting: extraction, synthesis, and filing."""
    filename = file_path.name
    ext = file_path.suffix.lower()

    if not manifest.should_process(file_path):
        return # Skip if already processed

    print(f"Background processing started for: {filename}")

    if ext in ['.png','.jpg']:
        print(f"Image detected: {os.path.basename(file_path)}")
        ai_data = model.synthesize_image(file_path)
        filer.file_source_note(os.path.basename(file_path), ai_data)
        taxsearcher.update_taxonomy(ai_data['core_concepts'])
        manifest.mark_processed(file_path)
        print(f"Wiki successfully updated for {filename}!")

    if ext == '.csv':
        # Direct accurate extraction for CSVs
        df = pd.read_csv(file_path)
        # Limit rows for the archive/wiki to keep files manageable
        raw_text = df.to_markdown(index=False) 
        
        # Archive the accurate table
        archive_path = WIKI_DIR / ".internal" / "raw_md" / f"{filename}.md"
        with open(archive_path, 'w', encoding='utf-8') as f:
            f.write(raw_text)

        # Synthesize: Pass only a summary or the column headers to the LLM 
        # to prevent it from hallucinating the data points.
        summary_prompt = f"CSV Headers: {list(df.columns)}. Preview: {df.head(10).to_string()}"
        ai_data = model.synthesize_source(summary_prompt, taxsearcher)
        
        filer.file_source_note(filename, ai_data)
        taxsearcher.update_taxonomy(ai_data['core_concepts'])
        manifest.mark_processed(file_path)
        print(f"Wiki successfully updated for {filename}!")

    if ext in ['.pdf', '.txt', '.docx']:
        # 1. Extract
        raw_text = ingester.extract_text(file_path)
        archive_path = WIKI_DIR / ".internal" / "raw_md" / f"{filename}.md"
        
        with open(archive_path, 'w', encoding='utf-8') as f:
            f.write(raw_text)
            
        # 2. Synthesize
        ai_data = model.synthesize_source(raw_text, taxsearcher)
        
        # 3. File & Update Taxonomy
        filer.file_source_note(filename, ai_data)
        taxsearcher.update_taxonomy(ai_data['core_concepts'])
        manifest.mark_processed(file_path)
        
        print(f"Wiki successfully updated for {filename}!")

# --- API ENDPOINTS ---

@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Accepts a file, saves it, and triggers background processing."""
    file_path = RAW_DIR / file.filename
    
    # Save the file to the raw directory
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Send the heavy processing to the background
    background_tasks.add_task(process_document, file_path)
    
    return {
        "status": "Accepted", 
        "message": f"{file.filename} is being processed in the background."
    }

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_question(query: QueryRequest):
    """Takes a question, searches the DB, and returns the LLM answer."""
    try:
        # Using your existing researcher logic
        answer, sources = researcher.ask(query.question, verbose=False)
        return {
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/graph-data")
async def get_graph_data():
    """Reads the local wiki and builds the node/edge graph for the UI."""
    nodes = []
    links = []
    added_nodes = set()

    def add_node(node_id, group, val):
        if node_id not in added_nodes:
            nodes.append({"id": node_id, "name": node_id, "group": group, "val": val})
            added_nodes.add(node_id)
    
    concepts_dir = WIKI_DIR / "concepts"
    if not concepts_dir.exists():
        return {"nodes": [], "links": []}

    for concept_file in concepts_dir.glob("*.md"):
        concept_name = concept_file.stem
        
        # Add the Concept Node (Group 1)
        if concept_name not in added_nodes:
            nodes.append({"id": concept_name, "name": concept_name, "group": 1, "val": 5})
            added_nodes.add(concept_name)
            
        # Read the file to find backlinks
        with open(concept_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Find all [[Linked Files]]
        linked_files = re.findall(r"\[\[(.*?)\]\]", content)
        
        for link in linked_files:
            # Filter out generic structural links
            if link not in ["Index", "Master_Taxonomy", "Concepts"]:
                # Add the Source File Node (Group 2) if it doesn't exist
                if link not in added_nodes:
                    nodes.append({"id": link, "name": link, "group": 2, "val": 3})
                    added_nodes.add(link)
                
                # Create the edge connecting the Concept to the Source File
                links.append({
                    "source": concept_name, 
                    "target": link
                })

    explorations_dir = WIKI_DIR / "explorations"
    if explorations_dir.exists():
        for exp_file in explorations_dir.glob("*.md"):
            exp_name = exp_file.stem
            add_node(exp_name, group=3, val=4) # Explorations are Group 3
            
            with open(exp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Connect the Exploration to the concepts and sources it mentions
            linked_files = re.findall(r"\[\[(.*?)\]\]", content)
            for link in linked_files:
                if link not in ["Index", "Master_Taxonomy", "Concepts"]:
                    add_node(link, group=2, val=3) # Ensure the target node exists
                    links.append({"source": exp_name, "target": link})
                
    return {"nodes": nodes, "links": links}

@app.get("/file/{filename:path}")
async def get_file_content(filename: str):
    """Fetches the markdown content of a clicked node."""
    
    # 1. Check if it's a Concept Note
    concept_path = WIKI_DIR / "concepts" / f"{filename}.md"
    if concept_path.exists():
        with open(concept_path, 'r', encoding='utf-8') as f:
            return {"title": filename, "content": f.read(), "type": "Concept"}
            
    # 2. Check if it's a Source Summary Note
    # Convert 'CaseStudy.pdf' -> 'CaseStudy.md'
    source_name = os.path.splitext(filename)[0] + ".md"
    source_path = WIKI_DIR / "sources" / source_name
    if source_path.exists():
        with open(source_path, 'r', encoding='utf-8') as f:
            return {"title": filename, "content": f.read(), "type": "Source Summary"}
            
    # 3. Check if it's a Raw Document
    raw_path = WIKI_DIR / ".internal" / "raw_md" / f"{filename}.md"
    if raw_path.exists():
        with open(raw_path, 'r', encoding='utf-8') as f:
            return {"title": filename, "content": f.read(), "type": "Raw Extracted Text"}

    exploration_path = WIKI_DIR / "explorations" / f"{filename}.md"
    if exploration_path.exists():
        with open(exploration_path, 'r', encoding='utf-8') as f:
            return {"title": filename, "content": f.read(), "type": "AI Exploration"}

    raise HTTPException(status_code=404, detail="File not found in Wiki.")

@app.get("/db-inspect")
async def inspect_database():
    """Dumps all concepts currently stored in the LanceDB vector database."""
    try:
        # Pull the table into a Pandas DataFrame, dropping the giant vector column for readability
        df = taxsearcher.table.to_pandas().drop(columns=['vector'])
        
        return {
            "total_concepts": len(df),
            "concepts": df.to_dict(orient="records")
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/save-exploration")
async def save_exploration_endpoint(data: ExplorationRequest):
    """Saves a good LLM response back into the wiki as a permanent note."""
    try:
        # Call the existing method on your researcher instance
        researcher.save_exploration(data.question, data.answer, data.sources)
        return {"status": "success", "message": "Exploration saved to knowledge base."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/dashboard-summary")
async def get_dashboard_summary():
    """Aggregates stats, recent files, and top concepts for the UI."""
    try:
        # 1. Fetch Recent Activity from Manifest
        all_processed = manifest.data.get("processed_files", {})
        # Sort by timestamp (stored as string in manifest) descending
        sorted_files = sorted(
            all_processed.items(), 
            key=lambda x: x[1].get("timestamp", "0"), 
            reverse=True
        )
        recent_activity = [
            {"name": name, "importance": meta.get("metadata", {}).get("importance", 5)}
            for name, meta in sorted_files[:5]
        ]

        # 2. Identify Top Concepts (Centrality)
        concepts_dir = WIKI_DIR / "concepts"
        concept_stats = []
        if concepts_dir.exists():
            for c_file in concepts_dir.glob("*.md"):
                with open(c_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Count backlinks (mentions of source files)
                links = re.findall(r"\[\[(.*?)\]\]", content)
                # Filter out structural links to count actual research connections
                connection_count = len([l for l in links if l not in ["Index", "Concepts"]])
                concept_stats.append({"name": c_file.stem, "connections": connection_count})
        
        top_concepts = sorted(concept_stats, key=lambda x: x["connections"], reverse=True)[:10]

        return {
            "stats": {
                "total_sources": len(all_processed),
                "total_concepts": len(concept_stats)
            },
            "recent_activity": recent_activity,
            "top_concepts": top_concepts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # This tells Python: "If I run this file directly, start the Uvicorn server!"
    print("Starting Librarian API on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)