import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from busqa.batch_evaluator import evaluate_conversations_high_speed
from tools.bulk_list_evaluate import evaluate_conversation_from_raw
from busqa.models import Conversation as BusQAConversation
from busqa.llm_client import LLMClient
from busqa.prompt_loader import load_unified_rubrics, load_diagnostics_config
from busqa.brand_specs import load_brand_prompt, get_available_brands, get_brand_prompt_path
from busqa.brand_resolver import BrandResolver
from busqa.aggregate import make_summary, generate_insights
from tools.bulk_list_evaluate import fetch_conversations_with_messages, select_conversations
from benchmark_performance import benchmark_batch_processing

# --- FastAPI App Initialization ---
app = FastAPI(
    title="BusQA LLM API",
    description="API for the Bus Quality Assurance LLM evaluation system.",
    version="1.0.0",
)

# --- CORS Middleware ---
# This is useful for local development if you run the frontend outside of Docker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Global Clients and Configs (Load once on startup) ---
try:
    rubrics_cfg = load_unified_rubrics()
    diagnostics_cfg = load_diagnostics_config()
    brand_resolver = BrandResolver(bot_map_path="config/bot_map.yaml")
    llm_client = LLMClient()
    available_brands = get_available_brands()
except Exception as e:
    print(f"FATAL: Could not load initial configurations. {e}")
    # In a real app, you might want to exit or have a fallback.
    rubrics_cfg = diagnostics_cfg = brand_resolver = llm_client = available_brands = None


# --- Pydantic Models for API I/O ---
class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None

class Conversation(BaseModel):
    conversation_id: str
    messages: List[Message]
    metadata: Optional[Dict[str, Any]] = None

class SingleEvaluationRequest(BaseModel):
    conversation: Conversation
    brand_id: str = Field(
        ...,
        description="The brand ID to use for evaluation, or 'auto-by-botid' for automatic detection."
    )
    model: str = Field(default="gemini-1.5-flash", description="The model to use for evaluation.")
    temperature: float = Field(default=0.2, description="The temperature to use for evaluation.")


class BatchEvaluationRequest(BaseModel):
    conversations: List[Conversation]
    brand_id: str = Field(
        ...,
        description="The brand ID to use for evaluation, or 'auto-by-botid' for automatic detection."
    )
    max_concurrency: int = Field(
        default=10,
        description="Maximum number of concurrent evaluation tasks."
    )

class BulkListRequest(BaseModel):
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format.")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format.")
    limit: int = Field(default=100, description="Maximum conversations to fetch.")
    strategy: str = Field(default="random", description="Selection strategy (e.g., 'random', 'longest').")
    brand_id: str = Field(
        ...,
        description="The brand ID to use for evaluation, or 'auto-by-botid' for automatic detection."
    )
    max_concurrency: int = Field(
        default=10,
        description="Maximum number of concurrent evaluation tasks."
    )
    bearer_token: str = Field(..., description="Bearer token for the external API.")


# --- API Endpoints ---

@app.on_event("startup")
async def startup_event():
    if not all([rubrics_cfg, diagnostics_cfg, brand_resolver, llm_client, available_brands]):
        raise RuntimeError("API cannot start due to missing initial configurations.")
    print("API started successfully with all configurations loaded.")

@app.get("/", summary="Health Check")
async def read_root():
    """Health check endpoint to confirm the API is running."""
    return {"status": "BusQA LLM API is running"}

@app.get("/configs/brands", summary="Get Available Brands")
async def get_brands():
    """Returns a list of all available brand IDs for evaluation."""
    return {"brands": available_brands}

@app.post("/evaluate/single", summary="Evaluate a Single Conversation")
async def evaluate_single(request: SingleEvaluationRequest):
    """
    Evaluates a single conversation against the specified brand's policies.
    """
    try:
        conversation_data = request.conversation.dict()
        brand_id = request.brand_id

        if brand_id == "auto-by-botid":
            bot_id = conversation_data.get("metadata", {}).get("bot_id")
            if not bot_id:
                raise HTTPException(status_code=400, detail="bot_id is required in metadata for 'auto-by-botid' mode.")
            brand_id = brand_resolver.resolve(bot_id)
            if not brand_id:
                raise HTTPException(status_code=404, detail=f"No brand mapping found for bot_id: {bot_id}")

        brand_prompt_path = get_brand_prompt_path(brand_id)
        if not brand_prompt_path:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")

        # evaluate_conversation_from_raw is a sync function, run in a thread
        result = await asyncio.to_thread(
            evaluate_conversation_from_raw,
            raw_conv=conversation_data,
            brand_prompt_path=brand_prompt_path,
            model=request.model,
            temperature=request.temperature,
        )
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/evaluate/batch", summary="Evaluate a Batch of Conversations")
async def evaluate_batch_conversations(request: BatchEvaluationRequest):
    """
    Evaluates a batch of conversations concurrently for high throughput.
    """
    try:
        results = await evaluate_conversations_high_speed(
            conversations=[c.dict() for c in request.conversations],
            brand_id=request.brand_id,
            max_concurrency=request.max_concurrency,
            llm_client=llm_client,
            rubrics_cfg=rubrics_cfg,
            diagnostics_cfg=diagnostics_cfg,
            brand_resolver=brand_resolver
        )
        
        summary = make_summary(results)
        insights = generate_insights(summary)
        
        return {
            "summary": summary,
            "insights": insights,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during batch evaluation: {str(e)}")

@app.post("/evaluate/batch/stream", summary="Stream batch evaluation results (SSE)")
async def evaluate_batch_stream(request: BatchEvaluationRequest):
    """
    Streams per-conversation results as they complete using Server-Sent Events (SSE).
    """
    try:
        queue: asyncio.Queue = asyncio.Queue()

        async def stream_callback(result: Dict[str, Any]):
            # Push each finished result to the queue for streaming
            await queue.put({"type": "item", "data": result})

        async def run_evaluation():
            try:
                results = await evaluate_conversations_high_speed(
                    conversations=[c.dict() for c in request.conversations],
                    brand_id=request.brand_id,
                    max_concurrency=request.max_concurrency,
                    llm_client=llm_client,
                    rubrics_cfg=rubrics_cfg,
                    diagnostics_cfg=diagnostics_cfg,
                    brand_resolver=brand_resolver,
                    stream_callback=stream_callback
                )
                summary = make_summary(results)
                insights = generate_insights(summary)
                await queue.put({"type": "summary", "data": {"summary": summary, "insights": insights}})
            except Exception as e:
                await queue.put({"type": "error", "error": str(e)})
            finally:
                await queue.put({"type": "done"})

        async def sse_event_generator():
            # Start evaluation in the background
            asyncio.create_task(run_evaluation())
            # Stream items as they arrive
            while True:
                event = await queue.get()
                if event.get("type") == "item":
                    yield f"data: {json.dumps(event['data'])}\n\n"
                elif event.get("type") == "summary":
                    yield f"event: summary\ndata: {json.dumps(event['data'])}\n\n"
                elif event.get("type") == "error":
                    yield f"event: error\ndata: {json.dumps({'message': event['error']})}\n\n"
                elif event.get("type") == "done":
                    yield "event: end\ndata: {}\n\n"
                    break

        return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start streaming batch evaluation: {str(e)}")

@app.post("/evaluate/bulk-list", summary="Fetch, Select, and Evaluate Conversations")
async def evaluate_from_bulk_list(request: BulkListRequest):
    """
    Fetches conversations from an external API, selects a subset based on a
    strategy, and evaluates them in a batch.
    """
    try:
        # 1. Create FetchConfig and then fetch conversations
        fetch_config = FetchConfig(
            base_url=os.getenv("API_BASE_URL", "http://103.141.140.243:14496"),
            bot_id=request.brand_id,  # Assuming brand_id can be used as bot_id here
            bearer_token=request.bearer_token,
            page_size=request.limit,
            max_pages=5 # A sensible default for bulk list
        )
        all_conversations = await asyncio.to_thread(fetch_conversations_with_messages, fetch_config)

        # 2. Select conversations
        selected_conversations = select_conversations(
            conversations=all_conversations,
            strategy=request.strategy,
            num_to_select=request.limit
        )

        if not selected_conversations:
            return {"message": "No conversations found or selected for the given criteria.", "results": []}

        # 3. Evaluate conversations
        results = await evaluate_conversations_high_speed(
            conversations=selected_conversations,
            brand_id=request.brand_id,
            max_concurrency=request.max_concurrency,
            llm_client=llm_client,
            rubrics_cfg=rubrics_cfg,
            diagnostics_cfg=diagnostics_cfg,
            brand_resolver=brand_resolver
        )
        
        summary = make_summary(results)
        insights = generate_insights(summary)
        
        return {
            "summary": summary,
            "insights": insights,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during bulk list evaluation: {str(e)}")

@app.get("/benchmark", summary="Run Performance Benchmark")
async def run_benchmark(
    min_concurrency: int = Query(5, description="Minimum concurrency level to test."),
    max_concurrency: int = Query(30, description="Maximum concurrency level to test."),
    step: int = Query(5, description="Step to increment concurrency."),
    num_tasks: int = Query(50, description="Number of dummy tasks to run for the benchmark.")
):
    """
    Benchmarks the batch processing system to find the optimal concurrency level.
    """
    try:
        # This function is synchronous, so we run it in a thread pool
        # to avoid blocking the event loop.
        loop = asyncio.get_event_loop()
        benchmark_results = await loop.run_in_executor(
            None, 
            benchmark_batch_processing,
            num_tasks,
            min_concurrency,
            max_concurrency,
            step
        )
        return {
            "message": "Benchmark completed.",
            "results": benchmark_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during benchmarking: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
