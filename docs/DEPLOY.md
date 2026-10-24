# Deploy (human actions)

Publishing is a human action (CLAUDE.md §4). Nothing here has been run.

## Local demo
```powershell
uv run python app.py            # http://127.0.0.1:7860 ; D uses local Ollama (LLM_PROFILE=local)
```
Set `C_MODEL_PATH` to the fine-tuned model folder to enable detector C. B uses the cached
`protectai-deberta` stand-in until Prompt Guard 2 is downloaded and the factory in `ui/service.py` is switched.

## Hugging Face dataset (hard negatives)
After you accept rows into `data_own/hard_negatives.jsonl`:
```powershell
huggingface-cli login
huggingface-cli upload <hf-user>/prompt-injection-hard-negatives data_own/hard_negatives.jsonl hard_negatives.jsonl --repo-type dataset
huggingface-cli upload <hf-user>/prompt-injection-hard-negatives data_own/README.md README.md --repo-type dataset
```

## Hugging Face Space (Gradio SDK)
Create a Space, copy `app.py`, `src/`, `configs/`, `reports/`, `data_own/`, `pyproject.toml`; Space variables:
`LLM_PROFILE=hosted`, `DEMO_MODE=true`; Space secret: `GROQ_API_KEY`. Record the URLs in WORKLOG.
