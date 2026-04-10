# imports
import os
import json
import hashlib
from pathlib import Path
from docling.document_converter import DocumentConverter
import ollama
from pydantic import BaseModel
from typing import List
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import urllib.parse
import base64
from sentence_transformers import SentenceTransformer
import lancedb
import numpy as np
import re
import pyarrow as pa

BASE_DIR = Path(".")
RAW_DIR = BASE_DIR / "raw"
WIKI_DIR = BASE_DIR / "wiki"
MANIFEST_PATH = BASE_DIR / "manifest.json"
ARCHIVE_DIR = WIKI_DIR / ".internal" / "raw_md"

for folder in [RAW_DIR, WIKI_DIR / "sources", WIKI_DIR / "concepts", ARCHIVE_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

model_version = "gemma4:e4b"

class ManifestManager:
    """Manages the 'State' of our wiki to prevent re-processing files."""
    def __init__(self, path):
        self.path = path
        self.data = self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path, 'r') as f:
                return json.load(f)
        return {"processed_files": {}, "version": "1.0"}

    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get_file_hash(self, file_path):
        """Creates a unique fingerprint for a file's contents."""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    # Checking if we should process the file
    def should_process(self, file_path):
        fname = os.path.basename(file_path)
        current_hash = self.get_file_hash(file_path)
        
        # Check if we've seen this exact file content before
        if fname in self.data["processed_files"]:
            if self.data["processed_files"][fname]["hash"] == current_hash:
                return False
        return True
    
    # Marking a file as processed
    def mark_processed(self, file_path, metadata=None):
        fname = os.path.basename(file_path)
        self.data["processed_files"][fname] = {
            "hash": self.get_file_hash(file_path),
            "timestamp": str(Path(file_path).stat().st_mtime),
            "metadata": metadata or {}
        }
        self.save()

class LibrarianIngester:
    """Converts any raw file to clean Markdown."""
    def __init__(self):
        self.md_converter = DocumentConverter()

    def extract_text(self, file_path):
        """
        Takes a file path and returns the raw Markdown text content.
        Supports: PDF, DOCX, XLSX, PPTX, HTML, Images, etc.
        """
        try:
            print(f"Extracting text from: {os.path.basename(file_path)}...")
            result = self.md_converter.convert(str(file_path))
            return result.document.export_to_markdown()

        except Exception as e:
            return f"Error during extraction: {str(e)}"

class Librarian:
    def __init__(self, model_name=model_version):
        self.model = model_name
        self.concepts_path = Path(WIKI_DIR) / "concepts"

    def get_existing_concepts(self):
        """Scans the wiki folder to see what topics we already have."""
        if not self.concepts_path.exists():
            return []
        # Get names of all .md files, minus the extension
        return [f.stem for f in self.concepts_path.glob("*.md")]

    def encode_image(self, image_path):
        """Converts an image file to a base64 string for Ollama."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def synthesize_image(self, image_path):
        """Specialized method for analyzing visual files."""
        img_base64 = self.encode_image(image_path)

        existing = self.get_existing_concepts()
        taxonomy_content = ", ".join(existing) if existing else "None"
        
        system_prompt = (
            "You are a professional research librarian. Your job is to extract "
            "key insights from raw images. You must return your answer in JSON format."
        )
        user_prompt = (
            "Analyze the following text:"
            f"1. Provide a title"
            f"2. A 3-sentence summary"
            f"3. A list of 3-5 core concepts"
            f"3a) Pick the most relevant concepts from the list of existing concepts: {taxonomy_content}."
            f"3b) If and ONLY IF a vital concept is missing, suggest a new one, keeping concepts concise and hierarchical"
            f"4. Rank its importance to a business analyst on a scale of 1-10."
            f"Output should take the form of:"
            f"title:"
            f"summary:"
            f"core_concepts:"
            f"importance:"
        )
        
        # In 2026, the 'images' parameter in Ollama's generate is the standard
        response = ollama.generate(
            model=self.model,
            system=system_prompt,
            prompt=user_prompt,
            images=[img_base64],
            format="json"
        )
        
        return json.loads(response['response'])

    def synthesize_source(self, raw_text, taxsearcher):
        """Sends raw text to Gemma 4 and receives a structured summary."""
        existing = taxsearcher.get_suggestions(raw_text)
        taxonomy_content = ", ".join(existing) if existing else self.get_existing_concepts()
        
        system_prompt = (
            "You are a professional research librarian. Your job is to extract "
            "key insights from raw text. You must return your answer in JSON format."
        )
        
        user_prompt = (
            f"Analyze the following text:"
            f"1. Provide a title"
            f"2. A 3-sentence summary"
            f"3. A list of 3-5 core concepts"
            f"3a) Pick the most relevant concepts from the list of existing concepts: {taxonomy_content}."
            f"3b) If and ONLY IF a vital concept is missing, suggest a new one, keeping concepts concise and hierarchical"
            f"4. Rank its importance to a business analyst on a scale of 1-10."
            f"Output should take the form of:"
            f"title:"
            f"summary:"
            f"core_concepts:"
            f"importance:\n\nTEXT:\n{raw_text[:16000]}" # Truncated for laptop memory safety
        )

        try:
            # We use the 'format' parameter to force JSON output
            response = ollama.generate(
                model=self.model,
                system=system_prompt,
                prompt=user_prompt,
                format="json",
                keep_alive="24h"
            )
            
            # Parse the string response into a Python Dictionary
            return json.loads(response['response'])

        except Exception as e:
            return {"error": f"Brain failure: {str(e)}"}
        
class FileManagement:
    """Writes and organizes the Obsidian Markdown files."""
    def __init__(self, wiki_base_path):
        self.wiki_path = Path(wiki_base_path)
        self.sources_path = self.wiki_path / "sources"
        self.concepts_path = self.wiki_path / "concepts"

    def file_source_note(self, source_filename, ai_data):
        """Creates a dedicated note for a specific raw file."""
        note_name = f"{source_filename[:-4]}.md"
        file_path = self.sources_path / note_name

        ext = os.path.splitext(source_filename)[1].lower()
        image_embed = f"![[{source_filename}]]\n\n" if ext in ['.jpg', '.jpeg', '.png'] else ""
        
        # Convert the concepts list into Obsidian-style [[Links]]
        linked_concepts = [f"[[{c}]]" for c in ai_data['core_concepts']]
        encoded_filename = urllib.parse.quote(source_filename)
        content = (
            f"--- \n"
            f"importance: {ai_data.get('importance', 5)}\n"
            f"type: source_summary\n"
            f"--- \n\n"
            f"# {ai_data['title']}\n\n"
            f"## Summary\n{ai_data['summary']}\n\n"
            f"## Concepts\n{', '.join(linked_concepts)}\n\n"
            f"--- \n"
            f"[[Index]] | [View Raw Source](../../raw/{encoded_filename})"
        )

        # content = (
        # f"--- \ntype: source_summary\n--- \n\n"
        # f"# {ai_data['title']}\n\n"
        # f"{image_embed}" # Displays the image at the top of the note
        # f"## AI Description\n{ai_data['summary']}\n\n"
        # f"## Concepts\n{', '.join(['[['+c+']]' for c in ai_data['core_concepts']])}"
        # )


        with open(file_path, 'w') as f:
            f.write(content)
        
        # Now, ensure the 'Concept' stubs exist
        for concept in ai_data['core_concepts']:
            self._ensure_concept_exists(concept, ai_data['title'], source_filename)

    def _ensure_concept_exists(self, concept_name, source_title, source_filename):
        """Creates or updates a 'Concept' note so the wiki is never broken."""
        concept_file = self.concepts_path / f"{concept_name}.md"
        
        backlink = f"* [[{source_filename}]] - {source_title}\n"

        if not concept_file.exists():
            # Create a brand new concept page
            content = (
                f"# Concept: {concept_name}\n\n"
                f"## Related Research\n"
                f"{backlink}"
            )
            with open(concept_file, 'w') as f:
                f.write(content)
        else:
            # If it exists, append the new source to the bottom
            with open(concept_file, 'a') as f:
                f.write(backlink)

class TaxonomySearcher:
    def __init__(self, db_path="./wiki/taxonomy_db"):
        self.db = lancedb.connect(db_path)
        # Load the tiny embedding model once
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Open the table (or create it if this is the first run)
        schema = pa.schema([
            pa.field("vector", pa.list_(pa.float32(), 384)), # Fixed size, float32
            pa.field("name", pa.string())
        ])

        # Create the table with the schema but NO data
        self.table = self.db.create_table(
            "concepts", 
            schema=schema, 
            exist_ok=True
        )

    def get_suggestions(self, doc_text, top_k=20):
        """Finds concepts similar to the document text."""
        # 1. Turn document text into a vector
        query_vector = self.encoder.encode(doc_text)
        
        # 2. Search LanceDB for the nearest concept names
        results = (self.table.search(query_vector)
                   .limit(top_k)
                   .to_list())
        
        # 3. Return just the names
        return [r["name"] for r in results if r["name"] != "initial"]
    
    def update_taxonomy(self, ai_suggested_concepts):
        """
        Takes a list of concepts (strings) from the AI, 
        filters out existing ones, and adds new ones to LanceDB.
        """
        # 1. Get the current list of concept names from the DB to avoid duplicates
        # For small/medium wikis, pulling the 'name' column is very fast
        existing_names = set(self.table.to_pandas()["name"].tolist())

        new_entries = []
        print(ai_suggested_concepts)
        for concept in ai_suggested_concepts:
            # Standardize to prevent 'AI' vs 'ai' duplicates
            clean_concept = concept.strip()
            
            if clean_concept not in existing_names:
                print(f"New Concept: {clean_concept}")
                
                # 2. Generate the embedding for the new concept
                vector = self.encoder.encode(clean_concept)
                
                new_entries.append({
                    "vector": vector.tolist(), 
                    "name": clean_concept
                })

        # 3. Batch add new entries to LanceDB
        if new_entries:
            self.table.add(new_entries)
            print(f"Successfully added {len(new_entries)} new concepts to the index.")

class LibrarianResearcher:
    def __init__(self, wiki_path, model=model_version):
        self.wiki_path = WIKI_DIR
        self.archive_path = ARCHIVE_DIR
        self.concepts_path = WIKI_DIR / 'concepts'
        self.db = lancedb.connect(self.wiki_path / "taxonomy_db")
        self.table = self.db.open_table("concepts")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.model = model
        self.associated_concepts = []

    def ask(self, question, verbose = False):
        print(f"Researching: {question}")
        
        # 1. RETRIEVAL: Find the best files
        # We search our vector DB for files related to the question
        query_vec = self.encoder.encode(question)
        search_results = self.table.search(query_vec).limit(5).to_list()
        self.associated_concepts = search_results
        all_research_files = []
        for concept in search_results:
            concept_name = concept['name']
            print(f"Checking Concept: {concept_name}")
            
            # 2. EXTRACT THE FILENAMES
            # Get the list of actual documents from the concept note
            docs = self.get_research_from_concept(concept_name)
            all_research_files.extend(docs)
        
        unique_files = list(set(all_research_files))
        context_parts = []
        
        for doc_name in unique_files:
            # We look in .internal/raw_md/ for the actual content
            archive_path = self.archive_path / f"{doc_name}.md"
            
            if archive_path.exists():
                with open(archive_path, 'r') as f:
                    context_parts.append(f"--- SOURCE: {doc_name} ---\n{f.read()}")
                    print(f"Loaded Raw Text: {doc_name}")

        context_block = "\n\n".join(context_parts)

        # 3. SYNTHESIS: Gemma 4 Reasons
        # We tell the AI to be a strict librarian who only uses the provided text
        system_prompt = (
            "You are a professional research agent. You must use a two-step process:\n"
            "1. <THOUGHT>: Analyze the provided context. List the specific snippets that "
            "relate to the question. Identify any contradictions or gaps.\n"
            "2. <ANSWER>: Provide the final response with [[Filename]] citations.\n\n"
            "If the answer is truly missing, use <THOUGHT> to explain WHY the provided "
            "documents didn't help."
        )
        
        
        user_prompt = f"CONTEXT:\n{context_block}\n\nQUESTION: {question}"

        response = ollama.generate(
            model=self.model,
            system=system_prompt,
            prompt=user_prompt,
            options={"temperature": 0.1} # Keep it factual and low-variance
        )

        if verbose:
            print(f"\n--- DEBUG INFO ---")
            print(f"Files retrieved: {all_research_files}")
            for i, part in enumerate(context_parts):
                # Print the first 200 characters of each retrieved file
                print(f"Snippet from {all_research_files[i]}: {part[:200]}...")
            print(f"----------------------\n")
        
        return response['response'], unique_files
    
    def get_research_from_concept(self, concept_name):
        """Parses an Obsidian Concept file to find all linked research documents."""
        concept_file = self.concepts_path / f"{concept_name}.md"
        if not concept_file.exists():
            return []

        with open(concept_file, 'r') as f:
            content = f.read()

        # REGEX: Finds all [[Links]] in the file
        # This will capture "CaseStudy.pdf" from [[CaseStudy.pdf]]
        links = re.findall(r"\[\[(.*?)\]\]", content)
        
        # Filter out common non-research links like 'Index' or 'Master_Taxonomy'
        research_links = [l for l in links if l not in ["Index", "Master_Taxonomy", "Concepts"]]
        return research_links
    
    def name_file(self, question, answer):
        system_prompt = (
            "Given a question and answer, name the file (less than 5 words) that will hold this information."
        )
        
        
        user_prompt = f"QUESTION:\n{question}\nANSWER:\n{answer}"

        response = ollama.generate(
            model=self.model,
            system=system_prompt,
            prompt=user_prompt,
            options={"temperature": 0.1} # Keep it factual and low-variance
        )

        return response['response']

    def save_exploration(self, question, answer, sources):
        explorations_dir = self.wiki_path / "explorations"
        explorations_dir.mkdir(exist_ok=True)

        sources = list(set(sources))
        query_vec = self.encoder.encode(answer)
        self.associated_concepts =  self.table.search(query_vec).limit(5).to_list()
        # Create a clean filename from the question
        file_name = self.name_file(question, answer)
        file_path = explorations_dir / f"{file_name}.md"
        
        with open(file_path, 'w') as f:
            f.write(f"# Exploration: {question}\n\n")
            f.write(f"## 🤖 AI Synthesis\n{answer}\n\n")
            f.write(f"## 📚 Sources Consulted\n")
            for s in sources:
                f.write(f"* [[{s}]]\n")
            f.write(f'## Concepts\n')
            for c in self.associated_concepts:
                f.write(f'* [[{c['name']}]]\n')
                
        print(f"Exploration saved to: {file_path}")


