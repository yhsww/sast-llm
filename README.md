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

**Branch:** `branch-1-direct-llm` (the `main` branch is maintained separately).

This version sends SonarQube findings directly to the selected LLM. It does not retrieve CWE/WSTG documents or add source-code snippets.

### Run

From the repository root, activate the virtual environment and install dependencies as described in section 1, then run:

```powershell
python query.py
```

The script discovers every `.json` file in `data/sast_reports`, including `GT01.json` through `GT08.json` and `sample.json` when present. Select one provider at the prompt. Pressing Enter uses `LLM_PROVIDER` from `.env`; option 5 explicitly runs all providers and may incur API costs.

You can also run a provider without an interactive prompt:

```powershell
python query.py --provider openai
python query.py --provider gemini
python query.py --provider kimi
python query.py --provider claude
```

To validate the input reports without calling any provider or creating results:

```powershell
python query.py --simulate
```

To test just one input, use its filename or stem:

```powershell
python query.py --only GT01 --simulate
python query.py --only sample.json --simulate
```

`run_experiment.py` is a compatibility entry point and delegates to `query.py`, so both commands follow the same execution path.

### Outputs

Successful outputs use stable names under `results/<provider-folder>/`, for example `results/GPT5.5/GT01_LLM.json` and `results/Gemini/sample_LLM.json`. The historical `GPT5.5` folder name is intentionally retained for compatibility even though the default OpenAI model is `gpt-4.1`. Re-running a successful report replaces its matching `*_LLM.json` atomically.

Failures are recorded separately as `*_ERROR.txt`; these files are ignored by Git and are not intended to be committed. A failed rerun does not delete a previously generated `*_LLM.json`.

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

After running `python query.py`, the script discovers the report JSON files, prompts for an LLM provider (unless `--provider`, `--all-providers`, or `--simulate` is used), and writes one stable output per report/provider.

The exact output depends on the input finding, model response, API configuration, and—on the RAG branches—the contents of the knowledge base and supplied code snippet.

## 7. Troubleshooting

- **`ModuleNotFoundError`:** activate `.venv` and run `pip install -r requirements.txt` again.
- **API authentication error:** check that the selected provider's API key is present in `.env` and valid. The `.env.example` contains placeholders only; copy it to `.env` and replace placeholders locally. Never commit real keys.
- **No retrieved context in Branch 2 or 3:** rerun the CWE/WSTG build commands and `python -m scripts.ingest --reset`.
- **Branch not found:** run `git fetch origin`, then `git branch -a` to inspect available branches.
- **PowerShell cannot activate the environment:** use the temporary execution-policy command shown in section 1.2.

## Important notes

- Run the commands from the repository root (the folder containing `requirements.txt` and `query.py`).
- Activate the virtual environment before installing dependencies or running the project.
- Branch 1 does not use RAG; Branches 2 and 3 use retrieval from the knowledge bases.
- Branch 3 additionally accepts source-code context.
- Never commit API keys or other secrets to the repository.
