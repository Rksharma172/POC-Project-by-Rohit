from src.config_loader import load_config
from sentence_transformers import SentenceTransformer

config = load_config()
_model = None

def get_model():
    global _model
    if _model is None:
        provider = config["embeddings"]["provider"]
        if provider == "bge":
            _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        elif provider == "e5":
            _model = SentenceTransformer("intfloat/e5-small-v2")
    return _model

def get_embedding(text):
    provider = config["embeddings"]["provider"]
    if provider in ["bge", "e5"]:
        model = get_model()
        return model.encode(text).tolist()
    elif provider == "openai":
        import os
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.embeddings.create(input=text, model="text-embedding-3-small")
        return response.data[0].embedding
    else:
        raise ValueError(f"Unknown provider: {provider}")
