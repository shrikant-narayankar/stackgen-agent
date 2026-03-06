#!/bin/bash
set -e

OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "⏳ Checking if model '$OLLAMA_MODEL' is available..."

# Check if the model exists in Ollama, if not pull it
MODEL_CHECK=$(curl -s "${OLLAMA_BASE_URL}/api/tags" | python -c "
import sys, json
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
print('found' if any('${OLLAMA_MODEL}' in m for m in models) else 'missing')
" 2>/dev/null || echo "missing")

if [ "$MODEL_CHECK" = "missing" ]; then
    echo "📥 Model '$OLLAMA_MODEL' not found. Pulling..."
    curl -s "${OLLAMA_BASE_URL}/api/pull" -d "{\"name\": \"${OLLAMA_MODEL}\"}" | while read -r line; do
        status=$(echo "$line" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null || true)
        if [ -n "$status" ]; then
            echo "   $status"
        fi
    done
    echo "✅ Model '$OLLAMA_MODEL' pulled successfully."
else
    echo "✅ Model '$OLLAMA_MODEL' is already available."
fi

echo "🚀 Starting agent..."
exec python src/main.py "$@"
