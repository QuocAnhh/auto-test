import json, re, time
import asyncio
from typing import Any, Dict
from concurrent.futures import ThreadPoolExecutor
from openai import AsyncOpenAI, OpenAI
import google.generativeai as genai

# Thread pool tối ưu cho Docker (giới hạn theo cores) - ULTRA HIGH PERFORMANCE
import os

# Make thread pool size configurable, with safer defaults
_env_workers = os.getenv("GEMINI_MAX_WORKERS")
try:
    _env_workers_int = int(_env_workers) if _env_workers else None
except Exception:
    _env_workers_int = None

_default_workers = max(8, (os.cpu_count() or 2) * 4)
_max_workers = min(64, _env_workers_int or _default_workers)
_gemini_executor = ThreadPoolExecutor(max_workers=_max_workers, thread_name_prefix="gemini")

# Global OpenAI client với connection pooling
_openai_client_cache = {}
_openai_async_client_cache = {}

def _get_openai_client(api_key: str, base_url: str = None) -> OpenAI:
    """Get cached OpenAI client với connection pooling"""
    cache_key = f"{api_key[:10]}_{base_url or 'default'}"
    if cache_key not in _openai_client_cache:
        _openai_client_cache[cache_key] = OpenAI(
            api_key=api_key, 
            base_url=base_url,
            max_retries=0  # Handle retries manually for better control
        )
    return _openai_client_cache[cache_key]

def _get_async_openai_client(api_key: str, base_url: str = None) -> AsyncOpenAI:
    """Get cached AsyncOpenAI client với connection pooling"""
    cache_key = f"{api_key[:10]}_{base_url or 'default'}"
    if cache_key not in _openai_async_client_cache:
        _openai_async_client_cache[cache_key] = AsyncOpenAI(
            api_key=api_key, 
            base_url=base_url,
            max_retries=0  # Handle retries manually
        )
    return _openai_async_client_cache[cache_key]

def call_llm(api_key: str, model: str, system_prompt: str, user_prompt: str, base_url: str | None = None, temperature: float = 0.2, max_retries: int = 3) -> Dict[str, Any]:
    """Gọi LLM với retry tối ưu cho batch processing"""
    if model.startswith("gemini"):
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": temperature,
            "response_mime_type": "application/json"
        }
        prompt = system_prompt + "\n\n" + user_prompt
        
        import random
        for attempt in range(max_retries + 1):
            try:
                model_obj = genai.GenerativeModel(model)
                resp = model_obj.generate_content(prompt, generation_config=generation_config)
                return json.loads(resp.text)
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(0.5 * (attempt + 1))  # Giảm sleep time
                else:
                    raise e
    else:
        client = _get_openai_client(api_key, base_url)
        
        for attempt in range(max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                content = resp.choices[0].message.content
                return json.loads(content)
            except Exception as e:
                # Thử parse partial JSON
                try:
                    if 'resp' in locals():
                        text = resp.choices[0].message.content or ""
                        m = re.search(r"\{.*\}", text, flags=re.S)
                        if m:
                            return json.loads(m.group(0))
                except:
                    pass
                
                if attempt < max_retries:
                    time.sleep(0.3 * (attempt + 1))  # Giảm sleep time
                else:
                    raise e


class LLMClient:
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.base_url = base_url
        if not self.api_key:
            raise ValueError("API key must be provided either as an argument or via GEMINI_API_KEY env var.")

    async def call_async(self, model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_retries: int = 3) -> Dict[str, Any]:
        return await call_llm_async(
            api_key=self.api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            base_url=self.base_url,
            temperature=temperature,
            max_retries=max_retries
        )

async def call_llm_async(api_key: str, model: str, system_prompt: str, user_prompt: str, base_url: str | None = None, temperature: float = 0.2, max_retries: int = 3) -> Dict[str, Any]:
    """Async version của call_llm cho true concurrent processing"""
    if model.startswith("gemini"):
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": temperature,
            "response_mime_type": "application/json"
        }
        prompt = system_prompt + "\n\n" + user_prompt
        
        def _gemini_call():
            """Isolated Gemini call để chạy trong thread pool riêng"""
            model_obj = genai.GenerativeModel(model)
            return model_obj.generate_content(prompt, generation_config=generation_config)
        
        for attempt in range(max_retries + 1):
            try:
                # Dùng thread pool riêng với nhiều workers - tăng timeout
                loop = asyncio.get_event_loop()
                resp = await asyncio.wait_for(
                    loop.run_in_executor(_gemini_executor, _gemini_call),
                    timeout=30.0  # Timeout 30s cho mỗi LLM call
                )
                return json.loads(resp.text)
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    backoff = 0.2 * (2 ** attempt) + random.uniform(0, 0.2)
                    await asyncio.sleep(min(5.0, backoff))
                else:
                    raise Exception(f"Gemini API timeout after 30s (attempt {attempt+1}/{max_retries+1})")
            except Exception as e:
                if attempt < max_retries:
                    backoff = 0.2 * (2 ** attempt) + random.uniform(0, 0.2)
                    await asyncio.sleep(min(5.0, backoff))
                else:
                    raise e
    else:
        # Sử dụng cached AsyncOpenAI client cho true async với connection pooling
        client = _get_async_openai_client(api_key, base_url)
        
        import random
        for attempt in range(max_retries + 1):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                content = resp.choices[0].message.content
                return json.loads(content)
            except Exception as e:
                # Thử parse partial JSON
                try:
                    if 'resp' in locals():
                        text = resp.choices[0].message.content or ""
                        m = re.search(r"\{.*\}", text, flags=re.S)
                        if m:
                            return json.loads(m.group(0))
                except:
                    pass
                
                if attempt < max_retries:
                    backoff = 0.2 * (2 ** attempt) + random.uniform(0, 0.2)
                    await asyncio.sleep(min(5.0, backoff))
                else:
                    raise e