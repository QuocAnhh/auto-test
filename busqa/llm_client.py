import json, re, time
from typing import Any, Dict
from openai import OpenAI
import google.generativeai as genai

def call_llm(api_key: str, model: str, system_prompt: str, user_prompt: str, base_url: str | None = None, temperature: float = 0.2, max_retries: int = 3) -> Dict[str, Any]:
    """Gọi LLM với retry tối ưu cho batch processing"""
    if model.startswith("gemini"):
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": temperature,
            "response_mime_type": "application/json"
        }
        prompt = system_prompt + "\n\n" + user_prompt
        
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
        client = OpenAI(api_key=api_key, base_url=base_url)
        
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
                if attempt < max_retries:
                    time.sleep(0.3 * (attempt + 1))
                else:
                    raise e