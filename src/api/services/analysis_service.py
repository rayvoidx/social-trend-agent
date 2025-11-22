"""
Python Analysis Microservice

FastAPI 서비스로 Python의 강점(ML, NLP, LLM)을 TypeScript API Gateway에 제공
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

# Import from existing Python agent
from src.agents.news_trend.tools import (
    analyze_sentiment,
    extract_keywords,
    summarize_trend
)
from src.integrations.llm import get_llm_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Python Analysis Service",
    description="High-performance ML/NLP analysis service for hybrid architecture",
    version="1.0.0"
)

# CORS (TypeScript API Gateway에서 호출)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션: 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Request/Response Models
# =============================================================================

class NewsItem(BaseModel):
    title: str
    description: str
    url: str
    source: str
    publishedAt: str
    content: str = ""


class SentimentRequest(BaseModel):
    items: List[Dict[str, Any]]


class KeywordRequest(BaseModel):
    items: List[Dict[str, Any]]


class SummarizeRequest(BaseModel):
    query: str
    normalized_items: List[Dict[str, Any]]
    analysis: Dict[str, Any]


# =============================================================================
# Health Check
# =============================================================================

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "service": "python-analysis",
        "version": "1.0.0"
    }


# =============================================================================
# Analysis Endpoints
# =============================================================================

@app.post("/api/analyze/sentiment")
async def sentiment_analysis(request: SentimentRequest):
    """
    감성 분석
    
    Python의 NLP 라이브러리를 활용한 고급 감성 분석
    (향후 Transformer 모델로 업그레이드 가능)
    """
    try:
        logger.info(f"Sentiment analysis started: {len(request.items)} items")
        result = analyze_sentiment(request.items)
        logger.info(f"Sentiment analysis completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/keywords")
async def keyword_extraction(request: KeywordRequest):
    """
    키워드 추출
    
    Python의 TF-IDF, Word2Vec 등을 활용한 키워드 추출
    """
    try:
        logger.info(f"Keyword extraction started: {len(request.items)} items")
        result = extract_keywords(request.items)
        logger.info(f"Keyword extraction completed: {result.get('total_unique_keywords')} keywords")
        return result
    except Exception as e:
        logger.error(f"Keyword extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/summarize")
async def summarization(request: SummarizeRequest):
    """
    LLM 기반 트렌드 요약
    
    LangChain Python의 성숙한 생태계를 활용한 고급 요약
    """
    try:
        logger.info(f"Summarization started: query={request.query}")
        result = summarize_trend(
            query=request.query,
            normalized_items=request.normalized_items,
            analysis=request.analysis
        )
        logger.info(f"Summarization completed: {len(result)} chars")
        return {"summary": result}
    except Exception as e:
        logger.error(f"Summarization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Batch Analysis (대량 처리)
# =============================================================================

@app.post("/api/analyze/batch")
async def batch_analysis(request: SentimentRequest):
    """
    배치 분석 (감성 + 키워드 + 요약 한 번에)
    
    Python에서 모든 분석을 한 번에 처리하여 네트워크 오버헤드 감소
    """
    try:
        logger.info(f"Batch analysis started: {len(request.items)} items")
        
        # 병렬 처리 (Python asyncio)
        sentiment = analyze_sentiment(request.items)
        keywords = extract_keywords(request.items)
        
        result = {
            "sentiment": sentiment,
            "keywords": keywords,
            "total_items": len(request.items)
        }
        
        logger.info("Batch analysis completed")
        return result
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Advanced ML Endpoints (향후 확장)
# =============================================================================

class MLPredictRequest(BaseModel):
    task: str  # "sentiment", "trend", "anomaly", "classification"
    texts: List[str]
    options: Dict[str, Any] = {}


class MLTrainRequest(BaseModel):
    task: str
    training_data: List[Dict[str, Any]]
    model_config: Dict[str, Any] = {}
    async_mode: bool = True


@app.post("/api/ml/predict")
async def ml_prediction(request: MLPredictRequest):
    """
    ML 모델 예측

    LLM 기반 예측 (트렌드 예측, 분류, 이상 탐지)
    """
    try:
        logger.info(f"ML prediction started: task={request.task}, items={len(request.texts)}")

        if request.task == "sentiment":
            return await _predict_sentiment(request.texts, request.options)
        elif request.task == "trend":
            return await _predict_trend(request.texts, request.options)
        elif request.task == "anomaly":
            return await _detect_anomaly(request.texts, request.options)
        elif request.task == "classification":
            return await _classify_texts(request.texts, request.options)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown task: {request.task}. Supported: sentiment, trend, anomaly, classification"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ML prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _predict_sentiment(texts: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 기반 감성 예측"""
    client = get_llm_client()

    prompt = f"""Analyze the sentiment of each text below and return a JSON array with predictions.

Texts:
{chr(10).join([f'{i+1}. {text[:500]}' for i, text in enumerate(texts[:20])])}

Return JSON format:
{{
    "predictions": [
        {{"text_index": 0, "sentiment": "positive"|"neutral"|"negative", "confidence": 0.0-1.0, "emotions": ["emotion1", "emotion2"]}}
    ],
    "summary": {{
        "positive_count": N,
        "neutral_count": N,
        "negative_count": N,
        "dominant_sentiment": "positive"|"neutral"|"negative"
    }}
}}"""

    result = client.chat_json(
        messages=[
            {"role": "system", "content": "You are a sentiment analysis expert. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return {
        "task": "sentiment",
        "predictions": result.get("predictions", []),
        "summary": result.get("summary", {}),
        "total_texts": len(texts)
    }


async def _predict_trend(texts: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 기반 트렌드 예측"""
    client = get_llm_client()

    time_horizon = options.get("time_horizon", "7d")

    prompt = f"""Analyze these texts and predict trends for the next {time_horizon}.

Texts:
{chr(10).join([f'- {text[:300]}' for text in texts[:15]])}

Return JSON format:
{{
    "predicted_trends": [
        {{"topic": "topic name", "direction": "rising"|"stable"|"declining", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}
    ],
    "emerging_topics": ["topic1", "topic2"],
    "declining_topics": ["topic1", "topic2"],
    "forecast_summary": "overall trend forecast"
}}"""

    result = client.chat_json(
        messages=[
            {"role": "system", "content": "You are a trend analysis expert. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return {
        "task": "trend",
        "time_horizon": time_horizon,
        "predicted_trends": result.get("predicted_trends", []),
        "emerging_topics": result.get("emerging_topics", []),
        "declining_topics": result.get("declining_topics", []),
        "forecast_summary": result.get("forecast_summary", "")
    }


async def _detect_anomaly(texts: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 기반 이상 탐지"""
    client = get_llm_client()

    prompt = f"""Analyze these texts and identify any anomalies, unusual patterns, or outliers.

Texts:
{chr(10).join([f'{i+1}. {text[:400]}' for i, text in enumerate(texts[:15])])}

Return JSON format:
{{
    "anomalies": [
        {{"text_index": 0, "anomaly_type": "type", "severity": "high"|"medium"|"low", "description": "why this is anomalous"}}
    ],
    "patterns": [
        {{"pattern": "description", "frequency": N, "significance": "high"|"medium"|"low"}}
    ],
    "overall_assessment": "summary of anomaly detection"
}}"""

    result = client.chat_json(
        messages=[
            {"role": "system", "content": "You are an anomaly detection expert. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return {
        "task": "anomaly",
        "anomalies": result.get("anomalies", []),
        "patterns": result.get("patterns", []),
        "overall_assessment": result.get("overall_assessment", ""),
        "total_texts": len(texts)
    }


async def _classify_texts(texts: List[str], options: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 기반 텍스트 분류"""
    client = get_llm_client()

    categories = options.get("categories", ["news", "opinion", "question", "announcement", "other"])

    prompt = f"""Classify each text into one of these categories: {', '.join(categories)}

Texts:
{chr(10).join([f'{i+1}. {text[:400]}' for i, text in enumerate(texts[:20])])}

Return JSON format:
{{
    "classifications": [
        {{"text_index": 0, "category": "category_name", "confidence": 0.0-1.0, "secondary_category": "optional"}}
    ],
    "category_distribution": {{
        "category_name": count
    }}
}}"""

    result = client.chat_json(
        messages=[
            {"role": "system", "content": "You are a text classification expert. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return {
        "task": "classification",
        "categories": categories,
        "classifications": result.get("classifications", []),
        "category_distribution": result.get("category_distribution", {}),
        "total_texts": len(texts)
    }


@app.post("/api/ml/train")
async def ml_training(request: MLTrainRequest):
    """
    ML 모델 학습 (Fine-tuning 또는 Few-shot Learning)

    Note: 실제 모델 학습은 백그라운드 작업으로 처리
    여기서는 Few-shot learning용 데이터 준비만 수행
    """
    try:
        logger.info(f"ML training started: task={request.task}, samples={len(request.training_data)}")

        if len(request.training_data) < 3:
            raise HTTPException(
                status_code=400,
                detail="At least 3 training samples required"
            )

        # Validate training data
        validated_data = []
        for item in request.training_data:
            if "text" not in item or "label" not in item:
                raise HTTPException(
                    status_code=400,
                    detail="Each training sample must have 'text' and 'label' fields"
                )
            validated_data.append({
                "text": item["text"][:1000],
                "label": item["label"]
            })

        # Build few-shot prompt template
        few_shot_examples = "\n".join([
            f"Text: {item['text'][:200]}\nLabel: {item['label']}"
            for item in validated_data[:5]
        ])

        # Test the few-shot learning
        client = get_llm_client()
        test_prompt = f"""You are trained to classify text with these examples:

{few_shot_examples}

Now classify this test text:
Text: {validated_data[-1]['text'][:200]}
Label:"""

        test_result = client.invoke(test_prompt)

        return {
            "status": "completed",
            "task": request.task,
            "training_samples": len(validated_data),
            "model_type": "few-shot-learning",
            "few_shot_template": few_shot_examples,
            "test_prediction": test_result.strip(),
            "expected_label": validated_data[-1]["label"],
            "note": "Few-shot learning template created. Use this template for inference."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ML training failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Python Analysis Service started")
    logger.info("   Ready to serve ML/NLP requests from TypeScript API")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 Python Analysis Service shutting down")


# =============================================================================
# Run Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9001,
        log_level="info"
    )

