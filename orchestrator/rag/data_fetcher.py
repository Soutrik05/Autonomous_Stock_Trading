# =============================================================================
# orchestrator/rag/data_fetcher.py
#
# Reads all educational PDFs (like Zerodha Varsity) from the knowledge_base/ 
# directory, extracts the text, and chunks it for the FAISS embedder.
# =============================================================================

import os
import logging
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "rag_db", "knowledge_base")

# ── 1. THE PAGE FILTER DICTIONARY ──
# Specify the exact pages you want to extract for specific PDFs. 
# Note: PyPDFLoader page numbers are 0-indexed (Page 1 = 0, Page 10 = 9)
# If a PDF is NOT in this dictionary, the script will process the entire file.
PAGE_FILTERS = {
    # Example: Only fetch Position Sizing and Trading Biases from Module 9 (Pages 84 to 110)
    "Module 9_Risk Management & Trading Psychology.pdf": range(84, 130),
    
    # Example: Only fetch the Corporate Actions chapter from Module 1
    "Module 1_Introduction.pdf": range(84, 100),
}

class DataFetcher:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            length_function=len,
        )

    def fetch_all(self) -> list:
        print("\n Reading Trading Strategy PDFs from Knowledge Base...\n")
        
        if not os.path.exists(KNOWLEDGE_DIR):
            os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
            print(f"  Created directory {KNOWLEDGE_DIR}. Please add PDFs here.")
            return []

        all_chunks = []
        pdf_files = [f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith('.pdf')]

        if not pdf_files:
            print("  No PDFs found in knowledge_base/ directory.")
            return []

        for filename in pdf_files:
            file_path = os.path.join(KNOWLEDGE_DIR, filename)
            
            try:
                # 1. Read the entire PDF into memory
                loader = PyPDFLoader(file_path)
                all_pages = loader.load()
                
                # 2. APPLY THE PAGE FILTER (The Magic Step)
                if filename in PAGE_FILTERS:
                    allowed_pages = PAGE_FILTERS[filename]
                    # Filter out any page whose metadata page number is not in our allowed range
                    pages_to_process = [p for p in all_pages if p.metadata.get('page') in allowed_pages]
                    print(f"  Processing: {filename} (Filtered to {len(pages_to_process)} specific pages)...")
                else:
                    pages_to_process = all_pages
                    print(f"  Processing: {filename} (All {len(pages_to_process)} pages)...")

                # If the filter resulted in 0 pages, skip to the next file
                if not pages_to_process:
                    logger.warning(f"No pages matched the filter for {filename}. Skipping.")
                    continue

                # 3. Chop the filtered pages into paragraphs
                chunks = self.text_splitter.split_documents(pages_to_process)
                
                # 4. Format for the Embedder
                for chunk in chunks:
                    all_chunks.append({
                        "text": f"Source: {filename} (Page {chunk.metadata.get('page', 0) + 1})\nContent: {chunk.page_content}",
                        "type": "strategy",
                        "symbol": "ALL"
                    })
            except Exception as e:
                logger.error(f"Failed to read {filename}: {e}")

        print(f"\n  Total strategy chunks generated: {len(all_chunks)}")
        return all_chunks