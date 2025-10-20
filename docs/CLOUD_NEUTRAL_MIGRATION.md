# Cloud-Neutral Migration Guide

**Date**: 2024-10-19
**Version**: 1.0.0

---

## Overview

This document describes the migration from Azure-specific configuration to a cloud-neutral architecture that supports multiple LLM providers and cloud services.

## Key Changes

### 1. Environment Variable Naming

All Azure-specific environment variable names have been changed to cloud-neutral names:

| Old (Azure-specific) | New (Cloud-neutral) |
|---------------------|---------------------|
| `AZURE_OPENAI_ENDPOINT` | `OPENAI_API_BASE` |
| `AZURE_OPENAI_DEPLOYMENT` | `OPENAI_DEPLOYMENT_NAME` |
| `AZURE_OPENAI_API_VERSION` | `OPENAI_API_VERSION` |
| `AZURE_OPENAI_API_KEY` | `OPENAI_API_KEY` |

**Why?**
- The new naming convention follows OpenAI's standard, which works for both Azure OpenAI and direct OpenAI API
- Makes it clear the system is not Azure-exclusive
- Easier for users of other cloud providers to understand

---

## 2. Multi-LLM Provider Support

### New Configuration Variable

```bash
LLM_PROVIDER=azure_openai  # Options: azure_openai, openai, anthropic, google, ollama
```

### Supported Providers

1. **Azure OpenAI** (default)
   ```bash
   LLM_PROVIDER=azure_openai
   OPENAI_API_TYPE=azure
   OPENAI_API_BASE=https://your-resource.openai.azure.com/
   OPENAI_API_KEY=your-api-key
   OPENAI_API_VERSION=2024-02-15-preview
   OPENAI_DEPLOYMENT_NAME=gpt-4
   OPENAI_MODEL_NAME=gpt-4
   ```

2. **OpenAI**
   ```bash
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-your-openai-api-key
   OPENAI_MODEL_NAME=gpt-4-turbo-preview
   ```

3. **Anthropic Claude**
   ```bash
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-your-key
   ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022
   ```

4. **Google Gemini**
   ```bash
   LLM_PROVIDER=google
   GOOGLE_API_KEY=your-google-api-key
   GOOGLE_MODEL_NAME=gemini-1.5-pro
   ```

5. **Ollama (Local)**
   ```bash
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL_NAME=llama3.2
   ```

---

## 3. Code Changes

### A. `backend/extension_modules/utils/model.py`

**Complete refactoring** to support multiple LLM providers:

```python
# Before
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

def mk_model():
    model = AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_deployment=AZURE_OPENAI_DEPLOYMENT,
        api_version=AZURE_OPENAI_API_VERSION,
        api_key=AZURE_OPENAI_API_KEY,
    )
    return model

# After
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "azure_openai")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-4")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4")

def mk_model(temperature: float = 0.1, max_tokens: int = 2000):
    """Create LLM model instance based on LLM_PROVIDER"""
    provider = LLM_PROVIDER.lower()

    if provider == "azure_openai":
        return _create_azure_openai_model(temperature, max_tokens)
    elif provider == "openai":
        return _create_openai_model(temperature, max_tokens)
    elif provider == "anthropic":
        return _create_anthropic_model(temperature, max_tokens)
    # ... etc
```

### B. `backend/extension_modules/pipes/base.py`

Updated environment variables and `_get_model()` method:

```python
# Before
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# After
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-4")
```

---

## 4. Configuration Files Updated

### Files Modified

1. **`.env`** - Production environment configuration
2. **`.env.example`** - Template with all supported providers
3. **`docker-compose.yaml`** - Docker environment variables
4. **`README.md`** - Updated environment variable documentation
5. **`docs/DESIGN_DOC.md`** - Updated architecture documentation
6. **`agents/news_trend_agent/README.md`** - Updated agent documentation

---

## 5. Migration Steps for Existing Users

### Step 1: Backup Current Configuration

```bash
cp .env .env.backup
```

### Step 2: Update Environment Variables

If you're using **Azure OpenAI** (most common):

```bash
# Old
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_API_KEY=your-api-key

# New
LLM_PROVIDER=azure_openai
OPENAI_API_TYPE=azure
OPENAI_API_BASE=https://your-resource.openai.azure.com/
OPENAI_DEPLOYMENT_NAME=gpt-4
OPENAI_MODEL_NAME=gpt-4
OPENAI_API_VERSION=2024-02-15-preview
OPENAI_API_KEY=your-api-key
```

### Step 3: Test the Configuration

```bash
# Test with sample data
python scripts/run_agent.py --agent news_trend_agent --query "AI trends" --window 7d
```

### Step 4: Switch Providers (Optional)

To switch from Azure OpenAI to direct OpenAI:

```bash
# Change these variables
LLM_PROVIDER=openai  # Change from azure_openai
OPENAI_API_KEY=sk-your-openai-api-key  # Your OpenAI API key
OPENAI_MODEL_NAME=gpt-4-turbo-preview  # OpenAI model name
# Remove or comment out Azure-specific variables
```

---

## 6. Docker Deployment

The `docker-compose.yaml` has been updated to support all LLM providers:

```yaml
environment:
  # LLM Configuration
  - LLM_PROVIDER=${LLM_PROVIDER:-azure_openai}
  - OPENAI_API_TYPE=${OPENAI_API_TYPE:-azure}
  - OPENAI_API_BASE=${OPENAI_API_BASE:-}
  - OPENAI_API_KEY=${OPENAI_API_KEY:-}
  - OPENAI_DEPLOYMENT_NAME=${OPENAI_DEPLOYMENT_NAME:-gpt-4}

  # Anthropic (optional)
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
  - ANTHROPIC_MODEL_NAME=${ANTHROPIC_MODEL_NAME:-claude-3-5-sonnet-20241022}

  # ... etc
```

---

## 7. Benefits of Cloud-Neutral Architecture

### Flexibility
- Switch between LLM providers without code changes
- Test different models for cost/performance optimization
- Avoid vendor lock-in

### Cost Optimization
- Use cheaper providers for development/testing
- Mix providers based on use case (e.g., Anthropic for analysis, OpenAI for summarization)
- Run locally with Ollama for offline development

### Reliability
- Failover to backup provider if primary is down
- Use multiple providers in production for redundancy

### Development
- Local development with Ollama (no API costs)
- Easy testing with different model capabilities

---

## 8. Backward Compatibility

**Important**: Old Azure-specific environment variables are **no longer supported**. You must update your configuration.

### Quick Migration Script

```bash
#!/bin/bash
# migrate_env.sh

if [ -f .env ]; then
    echo "Migrating .env to cloud-neutral format..."

    # Backup
    cp .env .env.pre_migration

    # Replace variables
    sed -i '' 's/AZURE_OPENAI_ENDPOINT/OPENAI_API_BASE/g' .env
    sed -i '' 's/AZURE_OPENAI_DEPLOYMENT/OPENAI_DEPLOYMENT_NAME/g' .env
    sed -i '' 's/AZURE_OPENAI_API_KEY/OPENAI_API_KEY/g' .env

    # Add new variables
    echo "LLM_PROVIDER=azure_openai" >> .env
    echo "OPENAI_API_TYPE=azure" >> .env

    echo "Migration complete! Check .env and update as needed."
    echo "Original backup saved to .env.pre_migration"
else
    echo "No .env file found. Please create one from .env.example"
fi
```

---

## 9. Troubleshooting

### Issue: "Unsupported LLM_PROVIDER" Error

**Cause**: Invalid value in `LLM_PROVIDER` environment variable

**Solution**:
```bash
# Check valid options
LLM_PROVIDER=azure_openai  # or openai, anthropic, google, ollama
```

### Issue: Old Azure Variables Not Working

**Cause**: System now uses cloud-neutral variable names

**Solution**: Update your `.env` file using the migration guide above

### Issue: Import Errors for LangChain Providers

**Cause**: Missing dependencies for specific providers

**Solution**:
```bash
# For Anthropic
pip install langchain-anthropic

# For Google
pip install langchain-google-genai

# For Ollama
pip install langchain-ollama
```

---

## 10. Next Steps

1. **Test Thoroughly**: Run your existing workflows to ensure everything works
2. **Update Documentation**: Update any internal docs referencing Azure-specific variables
3. **Explore Options**: Try different LLM providers for different use cases
4. **Monitor Costs**: Compare costs across providers

---

## Support

For questions or issues with the migration:
- Check [README.md](../README.md) for updated environment variable documentation
- Review [DESIGN_DOC.md](DESIGN_DOC.md) for architecture details
- Open an issue on GitHub

---

**Last Updated**: 2024-10-19
**Migration Version**: 1.0.0
**System Version**: Compatible with all versions post-migration
