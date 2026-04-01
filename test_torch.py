import sys
print("=== System Info ===")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

print("\n=== Torch Import ===")
try:
    import torch
    print(f"Torch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print("Torch import: SUCCESS ✅")
except Exception as e:
    print(f"Torch import FAILED ❌: {e}")

print("\n=== Transformers Import ===")
try:
    import transformers
    print(f"Transformers version: {transformers.__version__}")
    print("Transformers import: SUCCESS ✅")
except Exception as e:
    print(f"Transformers import FAILED ❌: {e}")

print("\n=== FinBERT Load Test ===")
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    print("Tokenizer loaded ✅")
    model = AutoModelForSequenceClassification.from_pretrained(
        "ProsusAI/finbert",
        use_safetensors=False
    )
    print("Model loaded ✅")
    print("FinBERT: SUCCESS ✅")
except Exception as e:
    print(f"FinBERT FAILED ❌: {e}")

print("\n=== Done ===")