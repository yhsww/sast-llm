# SAST Security Test Case Generator — Branch Execution Guide

This guide explains how to set up the project and run each branch from scratch.

## Project overview

The project generates SAST security test cases using a Large Language Model (LLM). The branches represent different approaches:

- **Branch 1 — Direct LLM (`main` / `branch-1-direct-llm`):** sends the finding directly to the LLM, without retrieval.
- **Branch 2 — RAG with CWE and WSTG (`branch-2-rag-cwe-wstg`):** retrieves supporting information from the CWE and WSTG knowledge bases.
- **Branch 3 — RAG with code context (`branch-3-rag-code-context`):** uses the knowledge bases and additional source-code snippets related to the finding.

## Requirements

- Python 3.11 or newer
- Git
- An OpenAI API key with access to the configured model

Commands below use **PowerShell** on Windows.

## 1. Initial setup

### 1.1 Clone the repository

If you have not cloned the repository yet:

```powershell
git clone https://github.com/yhsww/sast-llm.git
cd sast-llm
```

If the repository is already on your computer, open PowerShell in the project folder instead.

### 1.2 Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you may run this command for the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 1.3 Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 1.4 Configure environment variables

Create a `.env` file in the project root, following the variable names used in the project's configuration. Add your OpenAI API key, for example:

```env
OPENAI_API_KEY=your_api_key_here
```

Keep the real key private. Do not commit `.env` to Git or paste the key into source files.

## 2. Branch 1 — Direct LLM

**Branch:** `main` or `branch-1-direct-llm`

This version sends the finding to the LLM directly. It does not retrieve documents from the CWE/WSTG knowledge bases.

### Steps

1. Switch to the branch:

   ```powershell
   git switch branch-1-direct-llm
   ```

   If the project uses `main` as the direct-LLM branch, use:

   ```powershell
   git switch main
   ```

2. Run the query script:

   ```powershell
   python query.py
   ```

3. Follow the prompts and review the generated output.

## 3. Branch 2 — RAG with CWE and WSTG

**Branch:** `branch-2-rag-cwe-wstg`

This version retrieves context from two ChromaDB collections:

- `cwe_docs`
- `wstg_docs`

### Steps

1. Switch to the branch:

   ```powershell
   git switch branch-2-rag-cwe-wstg
   ```

2. Build the CWE knowledge base:

   ```powershell
   python -m scripts.build_cwe_kb
   ```

3. Build the WSTG knowledge base:

   ```powershell
   python -m scripts.build_wstg_kb
   ```

4. Ingest the documents into the vector database:

   ```powershell
   python -m scripts.ingest --reset
   ```

5. Run the query script:

   ```powershell
   python query.py
   ```

6. Follow the prompts and inspect the generated test cases.

> Run the knowledge-base build and ingestion steps when preparing the environment or whenever the source knowledge documents change.

## 4. Branch 3 — RAG with code context

**Branch:** `branch-3-rag-code-context`

This version combines the CWE/WSTG retrieval flow with source-code snippets associated with the finding.

### Steps

1. Switch to the branch:

   ```powershell
   git switch branch-3-rag-code-context
   ```

2. Build the CWE knowledge base:

   ```powershell
   python -m scripts.build_cwe_kb
   ```

3. Build the WSTG knowledge base:

   ```powershell
   python -m scripts.build_wstg_kb
   ```

4. Ingest the documents:

   ```powershell
   python -m scripts.ingest --reset
   ```

5. Run the query script:

   ```powershell
   python query.py
   ```

6. When prompted, paste the source-code snippet that corresponds to the finding. Finish the snippet input by entering:

   ```text
   ###
   ```

   If you do not want to provide a snippet, press Enter and then enter `###` when prompted.

### Snippet order for `sample.json`

When testing the findings in `sample.json`, use the corresponding snippets in this order:

1. `data/code_snippets/UserRepository.java`
2. `data/code_snippets/CommentController.java`
3. `data/code_snippets/DatabaseConfig.java`

Make sure each snippet matches the finding being analyzed.

## 5. Switching between branches

Before switching branches, save or commit any local changes you want to keep. Then run the command for the desired branch:

```powershell
git switch main
git switch branch-1-direct-llm
git switch branch-2-rag-cwe-wstg
git switch branch-3-rag-code-context
```

Run **one** of these commands at a time. The branch must exist locally. To list local branches:

```powershell
git branch
```

To update remote branch references:

```powershell
git fetch origin
git branch -a
```

If a branch exists only on the remote, create a local tracking branch with:

```powershell
git switch --track origin/branch-2-rag-cwe-wstg
```

Replace the branch name as needed.

## 6. Expected result

After running `python query.py`, the application should prompt for the SAST finding or related input and then generate a response using the approach implemented in the selected branch.

The exact output depends on the input finding, model response, API configuration, and—on the RAG branches—the contents of the knowledge base and supplied code snippet.

## 7. Troubleshooting

- **`ModuleNotFoundError`:** activate `.venv` and run `pip install -r requirements.txt` again.
- **API authentication error:** check that `OPENAI_API_KEY` is present in `.env` and valid.
- **No retrieved context in Branch 2 or 3:** rerun the CWE/WSTG build commands and `python -m scripts.ingest --reset`.
- **Branch not found:** run `git fetch origin`, then `git branch -a` to inspect available branches.
- **PowerShell cannot activate the environment:** use the temporary execution-policy command shown in section 1.2.

## Important notes

- Run the commands from the repository root (the folder containing `requirements.txt` and `query.py`).
- Activate the virtual environment before installing dependencies or running the project.
- Branch 1 does not use RAG; Branches 2 and 3 use retrieval from the knowledge bases.
- Branch 3 additionally accepts source-code context.
- Never commit API keys or other secrets to the repository.
