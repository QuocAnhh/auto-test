import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Body, Query, Form
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent))

from busqa.batch_evaluator import evaluate_conversations_high_speed
from tools.bulk_list_evaluate import evaluate_conversation_from_raw
from busqa.models import Conversation as BusQAConversation
from busqa.llm_client import LLMClient
from busqa.prompt_loader import load_unified_rubrics, load_diagnostics_config
from busqa.brand_specs import load_brand_prompt, get_available_brands, get_brand_prompt_path
from busqa.brand_resolver import BrandResolver
from busqa.aggregate import make_summary, generate_insights
from tools.bulk_list_evaluate import fetch_conversations_with_messages, select_conversations, FetchConfig
from busqa.batch_evaluator import evaluate_conversations_high_speed
# from benchmark_performance import benchmark_batch_processing

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

@app.get("/health", summary="Health Check")
async def read_root():
    """Health check endpoint to confirm the API is running."""
    return {"status": "BusQA LLM API is running"}

@app.get("/config/bearer-token", summary="Get Bearer Token")
async def get_bearer_token():
    """Get bearer token from environment"""
    bearer_token = os.getenv("BEARER_TOKEN")
    if bearer_token:
        return {"bearer_token": bearer_token}
    else:
        raise HTTPException(status_code=404, detail="Bearer token not found in environment")

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
        # Validate conversation data
        if not request.conversation.messages:
            raise HTTPException(status_code=400, detail="Conversation must have at least one message.")
        
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
        # Validate input
        if not request.conversations:
            raise HTTPException(status_code=400, detail="At least one conversation is required.")
        
        if request.max_concurrency < 1 or request.max_concurrency > 50:
            raise HTTPException(status_code=400, detail="max_concurrency must be between 1 and 50.")
        
        # Extract conversation IDs for batch evaluation
        conversation_ids = [c.conversation_id for c in request.conversations]
        
        # Get brand policy and prompt
        brand_prompt_path = get_brand_prompt_path(request.brand_id)
        if not brand_prompt_path:
            raise HTTPException(status_code=404, detail=f"Brand '{request.brand_id}' not found.")
        
        # Load brand policy and prompt
        brand_prompt_text, brand_policy = load_brand_prompt(brand_prompt_path)
        
        results = await evaluate_conversations_high_speed(
            conversation_ids=conversation_ids,
            base_url=os.getenv("API_BASE_URL", "http://103.141.140.243:14496"),  # Single conversation URL
            rubrics_cfg=rubrics_cfg,
            brand_policy=brand_policy,
            brand_prompt_text=brand_prompt_text,
            llm_api_key=os.getenv("GEMINI_API_KEY"),
            llm_model=request.model,
            temperature=0.2,
            llm_base_url=os.getenv("LLM_BASE_URL"),
            apply_diagnostics=True,
            diagnostics_cfg=diagnostics_cfg,
            max_concurrency=request.max_concurrency,
            brand_resolver=brand_resolver
        )
        
        summary = make_summary(results)
        insights = generate_insights(summary)
        
        return {
            "summary": summary,
            "insights": insights,
            "results": results
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during batch evaluation: {str(e)}")

@app.post("/evaluate/batch/stream", summary="Stream batch evaluation results (SSE)")
async def evaluate_batch_stream(request: BatchEvaluationRequest):
    """
    Streams per-conversation results as they complete using Server-Sent Events (SSE).
    """
    try:
        # Validate input
        if not request.conversations:
            raise HTTPException(status_code=400, detail="At least one conversation is required.")
        
        if request.max_concurrency < 1 or request.max_concurrency > 50:
            raise HTTPException(status_code=400, detail="max_concurrency must be between 1 and 50.")
        
        queue: asyncio.Queue = asyncio.Queue()

        async def stream_callback(result: Dict[str, Any]):
            # Push each finished result to the queue for streaming
            await queue.put({"type": "item", "data": result})

        async def run_evaluation():
            try:
                # Extract conversation IDs for batch evaluation
                conversation_ids = [c.conversation_id for c in request.conversations]
                
                # Get brand policy and prompt
                brand_prompt_path = get_brand_prompt_path(request.brand_id)
                if not brand_prompt_path:
                    await queue.put({"type": "error", "error": f"Brand '{request.brand_id}' not found."})
                    return
                
                # Load brand policy and prompt
                brand_policy = load_brand_policy(request.brand_id)
                brand_prompt_text = load_brand_prompt_text(brand_prompt_path)
                
                results = await evaluate_conversations_high_speed(
                    conversation_ids=conversation_ids,
                    base_url=os.getenv("API_BASE_URL", "http://103.141.140.243:14496"),  # Single conversation URL
                    rubrics_cfg=rubrics_cfg,
                    brand_policy=brand_policy,
                    brand_prompt_text=brand_prompt_text,
                    llm_api_key=os.getenv("GEMINI_API_KEY"),
                    llm_model=request.model,
                    temperature=0.2,
                    llm_base_url=os.getenv("LLM_BASE_URL"),
                    apply_diagnostics=True,
                    diagnostics_cfg=diagnostics_cfg,
                    max_concurrency=request.max_concurrency,
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
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start streaming batch evaluation: {str(e)}")

@app.post("/evaluate/bulk", summary="Bulk Evaluation - Fetch and Evaluate Conversations")
async def evaluate_bulk_conversations(
    bot_id: str = Form(..., description="Bot ID to fetch conversations from"),
    bearer_token: str = Form(..., description="Bearer token for API authentication"),
    limit: int = Form(10, description="Number of conversations to evaluate (1-100)"),
    strategy: str = Form("random", description="Selection strategy: random, newest, oldest, head, tail"),
    brand_id: str = Form("long_van", description="Brand ID for evaluation"),
          max_concurrency: int = Form(2, description="Maximum concurrency for evaluation (1-20)")
):
    """
    Simple bulk evaluation endpoint:
    1. Fetch conversations from bot_id using bearer_token
    2. Select N conversations based on strategy
    3. Evaluate them using the specified brand
    """
    try:
        # Validate input
        if not bot_id:
            raise HTTPException(status_code=400, detail="bot_id is required.")
        
        if not bearer_token:
            raise HTTPException(status_code=400, detail="bearer_token is required.")
        
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 100.")
        
        if max_concurrency < 1 or max_concurrency > 20:
            raise HTTPException(status_code=400, detail="max_concurrency must be between 1 and 20.")
        
        # 1. Fetch conversations from external API
        list_base_url = os.getenv("LIST_API_BASE_URL", "https://live-demo.agenticai.pro.vn")
        
        fetch_config = FetchConfig(
            base_url=list_base_url,
            bot_id=bot_id,
            bearer_token=bearer_token,
            page_size=min(limit * 2, 50),  # Fetch more to have options for selection
            max_pages=2  # Only fetch 2 pages max
        )
        
        try:
            all_conversations = await asyncio.to_thread(fetch_conversations_with_messages, fetch_config)
        except Exception as fetch_error:
            raise HTTPException(status_code=400, detail=f"Failed to fetch conversations: {str(fetch_error)}")

        if not all_conversations:
            return {"message": "No conversations found for the given bot_id.", "results": []}

        # 2. Select conversations
        selected_conversations = select_conversations(
            conversations=all_conversations,
            take=limit,
            strategy=strategy
        )

        if not selected_conversations:
            return {"message": "No conversations selected after filtering.", "results": []}

        # 3. Extract conversation IDs for evaluation
        conversation_ids = [conv.get("conversation_id") for conv in selected_conversations]
        
        # 4. Get brand configuration
        brand_prompt_path = get_brand_prompt_path(brand_id)
        if not brand_prompt_path:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
        
        brand_prompt_text, brand_policy = load_brand_prompt(brand_prompt_path)
        
        # 5. Evaluate conversations
        # Use single conversation URL for fetching individual messages
        single_base_url = os.getenv("API_BASE_URL", "http://103.141.140.243:14496")
        
        results = await evaluate_conversations_high_speed(
            conversation_ids=conversation_ids,
            base_url=single_base_url,  # Use single conversation URL for messages
            rubrics_cfg=rubrics_cfg,
            brand_policy=brand_policy,
            brand_prompt_text=brand_prompt_text,
            llm_api_key=os.getenv("GEMINI_API_KEY"),
            llm_model=request.model,
            temperature=0.2,
            llm_base_url=os.getenv("LLM_BASE_URL"),
            apply_diagnostics=True,
            diagnostics_cfg=diagnostics_cfg,
            max_concurrency=max_concurrency,
            brand_resolver=brand_resolver
        )
        
        # 6. Generate summary and insights
        try:
            # Debug: Log results structure
            print(f"DEBUG: Results count: {len(results)}")
            if results:
                print(f"DEBUG: First result keys: {list(results[0].keys())}")
                if "error" in results[0]:
                    print(f"DEBUG: First result error: {results[0]['error']}")
                if "result" in results[0]:
                    print(f"DEBUG: First result['result'] keys: {list(results[0]['result'].keys())}")
            
            summary = make_summary(results)
            insights = generate_insights(summary)
        except Exception as e:
            # Fallback summary if make_summary fails
            summary = {
                "count": len(results),
                "successful_count": len([r for r in results if "error" not in r]),
                "error_count": len([r for r in results if "error" in r]),
                "errors": [r for r in results if "error" in r],
                "avg_total_score": 0,
                "median_total_score": 0,
                "std_total_score": 0,
                "criteria_avg": {},
                "diagnostics_top": [],
                "flow_distribution": {},
                "policy_violation_rate": 0,
                "metrics_overview": {},
                "latency_stats": {}
            }
            insights = [f"⚠️ Lỗi tạo summary: {str(e)}"]
        
        return {
            "message": f"Successfully evaluated {len(results)} conversations",
            "summary": summary,
            "insights": insights,
            "results": results,
            "metadata": {
                "bot_id": bot_id,
                "brand_id": brand_id,
                "strategy": strategy,
                "total_fetched": len(all_conversations),
                "selected_count": len(selected_conversations),
                "evaluated_count": len(results)
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during bulk evaluation: {str(e)}")

@app.post("/test-token", summary="Test Bearer Token")
async def test_bearer_token_endpoint(request: dict = Body(...)):
    """Test if bearer token is valid"""
    try:
        base_url = request.get("base_url")
        bearer_token = request.get("bearer_token")
        
        if not base_url or not bearer_token:
            raise HTTPException(status_code=400, detail="base_url and bearer_token are required")
        
        # Test token using the existing function
        from tools.bulk_list_evaluate import test_bearer_token
        is_valid = await asyncio.to_thread(test_bearer_token, base_url, bearer_token)
        
        return {"valid": is_valid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token test failed: {str(e)}")

@app.post("/fetch-conversations", summary="Fetch Conversations")
async def fetch_conversations_endpoint(request: dict = Body(...)):
    """Fetch conversations from external API"""
    try:
        bot_id = request.get("bot_id")
        bearer_token = request.get("bearer_token")
        limit = request.get("limit", 10)
        strategy = request.get("strategy", "random")
        
        if not bot_id or not bearer_token:
            raise HTTPException(status_code=400, detail="bot_id and bearer_token are required")
        
        # Fetch conversations
        list_base_url = os.getenv("LIST_API_BASE_URL", "https://live-demo.agenticai.pro.vn")
        
        fetch_config = FetchConfig(
            base_url=list_base_url,
            bot_id=bot_id,
            bearer_token=bearer_token,
            page_size=min(limit * 2, 50),
            max_pages=2
        )
        
        all_conversations = await asyncio.to_thread(fetch_conversations_with_messages, fetch_config)
        
        if not all_conversations:
            return {"conversations": [], "message": "No conversations found"}
        
        # Select conversations
        selected_conversations = select_conversations(
            conversations=all_conversations,
            take=limit,
            strategy=strategy
        )
        
        return {
            "conversations": selected_conversations,
            "total_fetched": len(all_conversations),
            "selected_count": len(selected_conversations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversations: {str(e)}")

@app.post("/evaluate/bulk-raw", summary="Bulk Evaluation with Raw Data")
async def evaluate_bulk_raw(request: dict = Body(...)):
    """Evaluate conversations using raw data (no API fetching)"""
    try:
        conversations = request.get("conversations", [])
        brand_id = request.get("brand_id", "long_van")
        max_concurrency = request.get("max_concurrency", 2)
        model = request.get("model", "gemini-1.5-flash")
        
        if not conversations:
            raise HTTPException(status_code=400, detail="conversations are required")
        
        # Get brand configuration
        brand_prompt_path = get_brand_prompt_path(brand_id)
        if not brand_prompt_path:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
        
        brand_prompt_text, brand_policy = load_brand_prompt(brand_prompt_path)
        
        # Use evaluate_many_raw_conversations like Streamlit
        from tools.bulk_list_evaluate import evaluate_many_raw_conversations
        
        # Get appropriate API key based on model
        if model.startswith("gpt"):
            llm_api_key = os.getenv("OPENAI_API_KEY")
            llm_base_url = "https://api.openai.com/v1"
        else:
            llm_api_key = os.getenv("GEMINI_API_KEY")
            llm_base_url = os.getenv("LLM_BASE_URL")
        
        if not llm_api_key:
            raise HTTPException(status_code=400, detail=f"API key not found for model {model}")
        
        results = await evaluate_many_raw_conversations(
            raw_conversations=conversations,
            brand_prompt_path=brand_prompt_path,
            max_concurrency=max_concurrency,
            model=model,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url
        )
        
        # Generate summary and insights
        try:
            summary = make_summary(results)
            insights = generate_insights(summary)
        except Exception as e:
            # Fallback summary
            summary = {
                "count": len(results),
                "successful_count": len([r for r in results if "error" not in r]),
                "error_count": len([r for r in results if "error" in r]),
                "errors": [r for r in results if "error" in r],
                "avg_total_score": 0,
                "median_total_score": 0,
                "std_total_score": 0,
                "criteria_avg": {},
                "diagnostics_top": [],
                "flow_distribution": {},
                "policy_violation_rate": 0,
                "metrics_overview": {},
                "latency_stats": {}
            }
            insights = [f"⚠️ Lỗi tạo summary: {str(e)}"]
        
        return {
            "message": f"Successfully evaluated {len(results)} conversations",
            "summary": summary,
            "insights": insights,
            "results": results,
            "metadata": {
                "brand_id": brand_id,
                "total_conversations": len(conversations),
                "evaluated_count": len(results)
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during bulk evaluation: {str(e)}")


@app.post("/evaluate/bulk-raw-stream", summary="Bulk Evaluation with Raw Data (Streaming)")
async def evaluate_bulk_raw_stream(request: dict = Body(...)):
    """Evaluate conversations using raw data with streaming (SSE)"""
    try:
        conversations = request.get("conversations", [])
        brand_id = request.get("brand_id", "long_van")
        max_concurrency = request.get("max_concurrency", 2)
        model = request.get("model", "gemini-1.5-flash")
        
        if not conversations:
            raise HTTPException(status_code=400, detail="conversations are required")
        
        # Get brand configuration
        brand_prompt_path = get_brand_prompt_path(brand_id)
        if not brand_prompt_path:
            raise HTTPException(status_code=404, detail=f"Brand '{brand_id}' not found.")
        
        brand_prompt_text, brand_policy = load_brand_prompt(brand_prompt_path)
        
        # Get appropriate API key based on model
        if model.startswith("gpt"):
            llm_api_key = os.getenv("OPENAI_API_KEY")
            llm_base_url = "https://api.openai.com/v1"
        else:
            llm_api_key = os.getenv("GEMINI_API_KEY")
            llm_base_url = os.getenv("LLM_BASE_URL")
        
        if not llm_api_key:
            raise HTTPException(status_code=400, detail=f"API key not found for model {model}")
        
        # Use evaluate_many_raw_conversations with streaming
        from tools.bulk_list_evaluate import evaluate_many_raw_conversations
        
        async def stream_callback(result: Dict[str, Any]):
            # Push each finished result to the queue for streaming
            await result_queue.put({
                "type": "result",
                "data": result
            })
        
        # Create result queue for streaming
        result_queue = asyncio.Queue()
        
        # Start evaluation in background
        async def run_evaluation():
            try:
                results = await evaluate_many_raw_conversations(
                    raw_conversations=conversations,
                    brand_prompt_path=brand_prompt_path,
                    max_concurrency=max_concurrency,
                    model=model,
                    llm_api_key=llm_api_key,
                    llm_base_url=llm_base_url,
                    stream_callback=stream_callback
                )
                
                # Generate summary and insights
                try:
                    summary = make_summary(results)
                    insights = generate_insights(summary)
                except Exception as e:
                    # Fallback summary
                    summary = {
                        "count": len(results),
                        "successful_count": len([r for r in results if "error" not in r]),
                        "error_count": len([r for r in results if "error" in r]),
                        "errors": [r for r in results if "error" in r],
                        "avg_total_score": 0,
                        "median_total_score": 0,
                        "std_total_score": 0,
                        "criteria_avg": {},
                        "diagnostics_top": [],
                        "flow_distribution": {},
                        "policy_violation_rate": 0,
                        "metrics_overview": {},
                        "latency_stats": {}
                    }
                    insights = [f"⚠️ Lỗi tạo summary: {str(e)}"]
                
                # Send final summary
                await result_queue.put({
                    "type": "summary",
                    "data": {
                        "summary": summary,
                        "insights": insights,
                        "metadata": {
                            "brand_id": brand_id,
                            "total_conversations": len(conversations),
                            "evaluated_count": len(results)
                        }
                    }
                })
                
                # Send completion signal
                await result_queue.put({
                    "type": "complete",
                    "data": {"message": f"Successfully evaluated {len(results)} conversations"}
                })
                
            except Exception as e:
                await result_queue.put({
                    "type": "error",
                    "data": {"error": str(e)}
                })
        
        # Start evaluation task
        evaluation_task = asyncio.create_task(run_evaluation())
        
        async def sse_event_generator():
            try:
                while True:
                    try:
                        # Wait for next result with timeout
                        result = await asyncio.wait_for(result_queue.get(), timeout=1.0)
                        
                        if result["type"] == "complete":
                            yield f"data: {json.dumps(result)}\n\n"
                            break
                        elif result["type"] == "error":
                            yield f"data: {json.dumps(result)}\n\n"
                            break
                        else:
                            yield f"data: {json.dumps(result)}\n\n"
                            
                    except asyncio.TimeoutError:
                        # Send keep-alive
                        yield f"data: {json.dumps({'type': 'keepalive', 'data': {}})}\n\n"
                        continue
                        
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'data': {'error': str(e)}})}\n\n"
            finally:
                # Clean up
                if not evaluation_task.done():
                    evaluation_task.cancel()
        
        return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during bulk evaluation: {str(e)}")


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
        # TODO: Implement benchmark functionality
        # For now, return a mock response
        return {
            "message": "Benchmark functionality not yet implemented.",
            "results": {
                "optimal_concurrency": 15,
                "max_throughput": 25.5,
                "recommendations": ["Use concurrency 15-20 for optimal performance"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during benchmarking: {str(e)}")


# --- Prompt Doctor API Endpoints ---

class PromptAnalysisRequest(BaseModel):
    """Request model for prompt analysis."""
    evaluation_summary: Dict[str, Any] = Field(..., description="Evaluation summary from make_summary()")
    brand_id: str = Field(..., description="Brand ID to analyze prompt for")
    brand_policy: Optional[str] = Field(None, description="Optional brand policy text")

@app.post("/analyze/prompt-suggestions", summary="Analyze Prompt and Get Improvement Suggestions")
async def analyze_prompt_suggestions(request: PromptAnalysisRequest):
    """
    Analyzes a brand's prompt based on evaluation summary and provides specific improvement suggestions.
    """
    try:
        from busqa.prompt_doctor import analyze_prompt_suggestions
        from busqa.brand_specs import load_brand_prompt
        
        # Load brand prompt
        brand_prompt_path = get_brand_prompt_path(request.brand_id)
        brand_prompt_text, brand_policy_default = load_brand_prompt(brand_prompt_path)
        if not brand_prompt_text:
            raise HTTPException(status_code=404, detail=f"Brand prompt not found for brand: {request.brand_id}")
        
        # Use provided brand policy or load default
        brand_policy = request.brand_policy or brand_policy_default or ""
        
        # Analyze prompt suggestions
        result = await analyze_prompt_suggestions(
            evaluation_summary=request.evaluation_summary,
            current_prompt=brand_prompt_text,
            brand_policy=brand_policy
        )
        
        return {
            "brand_id": request.brand_id,
            "analysis": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during prompt analysis: {str(e)}")

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Serve frontend at root
@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the main frontend page"""
    from fastapi.responses import FileResponse
    import os
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path, media_type="text/html")
    else:
        return {"message": "Frontend not found. Please ensure frontend files are in the correct location."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
